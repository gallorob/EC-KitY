"""
This module implements the Algorithm class.
"""

from abc import abstractmethod

import random
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from time import time

from overrides import overrides

from eckity.event_based_operator import Operator
from eckity.population import Population
from eckity.statistics.statistics import Statistics
from eckity.subpopulation import Subpopulation

SEED_MIN_VALUE = 0
SEED_MAX_VALUE = 1000000


class Algorithm(Operator):
	"""
	Evolutionary algorithm to be executed.

	Abstract Algorithm that can be extended to concrete algorithms such as SimpleAlgorithm.

	Parameters
	----------
	population: Population
		The population to be evolved. Consists of a list of individuals.

	statistics: Statistics or list of Statistics, default=None
		Provide multiple statistics on the population during the evolutionary run.

    breeder: Breeder, default=SimpleBreeder()
        Responsible for applying the selection method and operator sequence on the individuals
        in each generation. Applies on one sub-population in simple case.

    population_evaluator: PopulationEvaluator, default=SimplePopulationEvaluator()
        Responsible for evaluating each individual's fitness concurrently and returns the best
         individual of each subpopulation (returns a single individual in simple case).

	max_generation: int, default=1000
		Maximal number of generations to run the evolutionary process.
		Note the evolution could end before reaching max_generation,
		depends on the termination checker.

	events: dict(str, dict(object, function)), default=None
		Dictionary of events, where each event holds a dictionary of (subscriber, callback method).

	event_names: list of strings, default=None
		Names of events to publish during the evolution.

    termination_checker: TerminationChecker, default=ThresholdFromTargetTerminationChecker()
        Responsible for checking if the algorithm should finish before reaching max_generation.

	max_workers: int, default=None
		Maximal number of worker nodes for the Executor object
		that evaluates the fitness of the individuals.

	random_generator: module, default=random
		Random generator module.

	random_seed: float or int, default=current system time
		Random seed for deterministic experiment.

	generation_seed: int, default=None
		Current generation seed. Useful for resuming a previously paused experiment.

	generation_num: int, default=0
		Current generation number

	Attributes
	----------
	final_generation_: int
		The generation in which the evolution ended.
	"""

	def __init__(self,
				 population,
				 statistics=None,
				 breeder=None,
				 population_evaluator=None,
				 termination_checker=None,
				 max_generation=None,
				 events=None,
				 event_names=None,
				 random_generator=None,
				 random_seed=time(),
				 generation_seed=None,
				 executor='thread',
				 max_workers=None,
				 generation_num=0):

		ext_event_names = event_names.copy() if event_names is not None else []

		ext_event_names.extend(["init", "evolution_finished", "after_generation"])
		super().__init__(events=events, event_names=ext_event_names)

		# Assert valid population input
		if population is None:
			raise ValueError('Population cannot be None')

		if isinstance(population, Population):
			self.population = population
		elif isinstance(population, Subpopulation):
			self.population = Population([population])
		elif isinstance(population, list):
			if len(population) == 0:
				raise ValueError('Population cannot be empty')
			for sub_pop in population:
				if not isinstance(sub_pop, Subpopulation):
					raise ValueError('Detected a non-Subpopulation '
									 'instance as an element in Population')
			self.population = Population(population)
		else:
			raise ValueError(
				'Parameter population must be either a Population, '
				'a Subpopulation or a list of Subpopulations\n '
				'received population with unexpected type of', type(population)
			)

		# Assert valid statistics input
		if isinstance(statistics, Statistics):
			self.statistics = [statistics]
		elif isinstance(statistics, list):
			for stat in statistics:
				if not isinstance(stat, Statistics):
					raise ValueError('Expected a Statistics instance as an element'
									 ' in Statistics list, but received', type(stat))
			self.statistics = statistics
		else:
			raise ValueError(
				'Parameter statistics must be either a subclass of Statistics'
				' or a list of subclasses of Statistics.\n'
				'received statistics with unexpected type of', type(statistics)
			)

		self.breeder = breeder
		self.population_evaluator = population_evaluator
		self.termination_checker = termination_checker
		self.max_generation = max_generation

		if random_generator is None:
			random_generator = random

		self.random_generator = random_generator
		self.random_seed = random_seed
		self.generation_seed = generation_seed

		self.best_of_run_ = None
		self.worst_of_gen = None
		self.generation_num = generation_num

		self.max_workers = max_workers

		if executor == 'thread':
			self.executor = ThreadPoolExecutor(max_workers=max_workers)
		elif executor == 'process':
			self.executor = ProcessPoolExecutor(max_workers=max_workers)
		else:
			raise ValueError('Executor must be either "thread" or "process"')
		self._executor_type = executor
		

		self.final_generation_ = 0

	@overrides
	def apply_operator(self, payload):
		"""
		begin the evolutionary run
		"""
		self.evolve()

	def evolve(self):
		"""
		Performs the evolutionary run by initializing the random seed, creating the population,
		performing the evolutionary loop and finally finishing the evolution process
		"""
		self.initialize()

		if self.termination_checker.should_terminate(self.population,
													 self.best_of_run_,
													 self.generation_num):
			self.final_generation_ = 0
			self.publish('after_generation')
		else:
			self.evolve_main_loop()

		self.finish()
		self.publish('evolution_finished')

	@abstractmethod
	def execute(self, **kwargs):
		"""
		Execute the algorithm result after evolution ended.

		Parameters
		----------
		kwargs : keyword arguments (relevant in GP representation)
			Input to program, including every variable in the terminal set as a keyword argument.
			For example, if `terminal_set=['x', 'y', 'z', 0, 1, -1]`
			then call `execute(x=..., y=..., z=...)`.

		Returns
		-------
		object
			Result of algorithm execution (for example: the best
			 individual in GA, or the best individual execution in GP)
		"""
		raise ValueError("execute is an abstract method in class Algorithm")

	def initialize(self):
		"""
		Initialize the algorithm before beginning the evolution process

        Initialize seed, Executor and relevant operators
        """
		self.set_random_seed(self.random_seed)
		print('debug: random seed =', self.random_seed)
		self.population_evaluator.set_executor(self.executor)

		for field in self.__dict__.values():
			if isinstance(field, Operator):
				field.initialize()

		self.create_population()
		self.best_of_run_ = self.population_evaluator.act(self.population)
		self.publish('init')

	def evolve_main_loop(self):
		"""
		Performs the evolutionary main loop
		"""
		for gen in range(self.max_generation):
			self.generation_num = gen

			self.set_generation_seed(self.next_seed())
			self.generation_iteration(gen)
			if self.termination_checker.should_terminate(self.population,
														 self.best_of_run_,
														 self.generation_num):
				self.final_generation_ = gen
				self.publish('after_generation')
				break
			self.publish('after_generation')

		self.executor.shutdown()

	@abstractmethod
	def generation_iteration(self, gen):
		"""
		Performs an iteration of the evolutionary main loop

		Parameters
		----------
		gen: int
			current generation number

		Returns
		-------
		bool
			True if the main loop should terminate, False otherwise
		"""
		raise ValueError("generation_iteration is an abstract method in class Algorithm")

	@abstractmethod
	def finish(self):
		"""
		Finish the evolutionary run
		"""
		raise ValueError("finish is an abstract method in class Algorithm")

	def set_generation_seed(self, seed):
		"""
		Set the seed for current generation

		Parameters
		----------
		seed: int
			current generation seed
		"""
		self.random_generator.seed(seed)
		self.generation_seed = seed

	def create_population(self):
		"""
		Create the population for the evolutionary run
		"""
		self.population.create_population_individuals()

	def event_name_to_data(self, event_name):
		"""
		Convert a given event name to relevant data of the Algorithm for the event

		Parameters
		----------
		event_name: string
			name of the event that is happening

		Returns
		----------
		dict
			Algorithm data regarding the given event
		"""
		if event_name == "init":
			return {"population": self.population,
					"statistics": self.statistics,
					"breeder": self.breeder,
					"termination_checker": self.termination_checker,
					"max_generation": self.max_generation,
					"events": self.events,
					"max_workers": self.max_workers}
		return {}

	def set_random_generator(self, rng):
		"""
		Set random generator object

		Parameters
		----------
		rng: object
			random number generator
		"""
		self.random_generator = rng

	def set_random_seed(self, seed=None):
		"""
		Set random seed

		Parameters
		----------
		seed: int
			random seed number
		"""
		self.random_generator.seed(seed)
		self.random_seed = seed

	def next_seed(self):
		"""
		Generate a random seed

		Returns
		----------
		int
			random seed number
		"""
		return self.random_generator.randint(SEED_MIN_VALUE, SEED_MAX_VALUE)

	# Necessary for valid pickling, since SimpleQueue object cannot be pickled
	def __getstate__(self):
		state = self.__dict__.copy()
		del state['executor']
		del state['random_generator']

		return state

	# Necessary for valid unpickling, since SimpleQueue object cannot be pickled
	def __setstate__(self, state):
		self.__dict__.update(state)
		if self._executor_type == 'thread':
			self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
		else:
			self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
		self.random_generator = random
