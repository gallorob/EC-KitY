from time import time

from eckity.algorithms.simple_evolution import SimpleEvolution
from eckity.breeders.simple_breeder import SimpleBreeder
from eckity.creators.gp_creators.full import FullCreator
from eckity.genetic_encodings.gp.tree.functions import f_and, f_or, f_not, f_if_then_else
from eckity.genetic_operators.crossovers.subtree_crossover import SubtreeCrossover
from eckity.genetic_operators.mutations.subtree_mutation import SubtreeMutation
from eckity.genetic_operators.selections.tournament_selection import TournamentSelection
from eckity.statistics.best_average_worst_statistics import BestAverageWorstStatistics
from eckity.subpopulation import Subpopulation
from eckity.termination_checkers.threshold_from_target_termination_checker import ThresholdFromTargetTerminationChecker
from examples.treegp.non_sklearn_mode.multiplexer.mux_evaluator \
    import MuxEvaluator, NUM_SELECT_ENTRIES, NUM_INPUT_ENTRIES


def main():
    """
    The goal in the Multiplexer (Mux) problem to create a GP tree that approximates a Multiplexer logical gate.

    Expected run time: less than a minute (on 2 cores, 2.5 GHz CPU)
    Example output (s - select inputs, d - data inputs):
    f_if_then_else
       f_and
          f_not
             f_if_then_else
                f_or
                   f_and
                      f_not
                         s1
                      f_if_then_else
                         f_not
                            f_or
                               s0
                               f_or
                                  f_and
                                     s0
                                     d3
                                  f_and
                                     d0
                                     s1
                         f_and
                            d1
                            s2
                         f_and
                            f_or
                               d4
                               f_and
                                  f_not
                                     s1
                                  f_if_then_else
                                     f_not
                                        f_or
                                           s0
                                           d5
                                     f_and
                                        d5
                                        f_if_then_else
                                           f_not
                                              d2
                                           f_not
                                              d4
                                           f_if_then_else
                                              d5
                                              d7
                                              d6
                                     f_and
                                        d1
                                        f_if_then_else
                                           d1
                                           s2
                                           d0
                            f_and
                               d5
                               d5
                   f_and
                      f_if_then_else
                         f_if_then_else
                            s2
                            s2
                            s2
                         d7
                         d2
                      s1
                d7
                f_if_then_else
                   f_and
                      f_if_then_else
                         d2
                         f_if_then_else
                            d3
                            d7
                            d7
                         f_if_then_else
                            d0
                            s1
                            d7
                      s1
                   s1
                   d7
          d7
       s1
       f_or
          f_and
             f_not
                s1
             f_if_then_else
                f_not
                   f_or
                      s0
                      f_or
                         f_and
                            d4
                            d0
                         f_and
                            f_if_then_else
                               d2
                               f_if_then_else
                                  d3
                                  f_and
                                     f_or
                                        f_and
                                           d2
                                           f_and
                                              1
                                              d7
                                        d1
                                     f_if_then_else
                                        d5
                                        f_or
                                           d0
                                           f_and
                                              d0
                                              d4
                                        f_if_then_else
                                           f_if_then_else
                                              d0
                                              d0
                                              d7
                                           f_or
                                              d2
                                              d7
                                           s0
                                  d7
                               f_if_then_else
                                  d0
                                  s1
                                  d7
                            s1
                f_and
                   d1
                   f_if_then_else
                      s2
                      s2
                      d0
                f_and
                   f_or
                      d4
                      f_and
                         f_not
                            s1
                         f_if_then_else
                            s2
                            s2
                            s2
                   f_and
                      d5
                      d5
          f_and
             f_if_then_else
                f_if_then_else
                   f_and
                      d5
                      d5
                   s2
                   s2
                d7
                d2
             s1

    References
    ----------
    DEAP Multiplexer Example: https://deap.readthedocs.io/en/master/examples/gp_multiplexer.html
    """
    start_time = time()

    # The terminal set of the tree will contain the mux inputs (d0-d7 in a 8-3 mux gate),
    # 3 select lines (s0-s2 in a 8-3 mux gate) and the constants 0 and 1
    select_terminals = [f's{i}' for i in range(NUM_SELECT_ENTRIES)]
    input_terminals = [f'd{i}' for i in range(NUM_INPUT_ENTRIES)]
    terminal_set = select_terminals + input_terminals + [0, 1]

    # Logical functions: and, or, not and if-then-else
    function_set = [f_and, f_or, f_not, f_if_then_else]

    # Initialize SimpleEvolution instance
    algo = SimpleEvolution(
        Subpopulation(creators=FullCreator(init_depth=(2, 4),
                                           terminal_set=terminal_set,
                                           function_set=function_set,
                                           bloat_weight=0.00001),
                      population_size=40,
                      # user-defined fitness evaluation method
                      evaluator=MuxEvaluator(),
                      # this is a maximization problem (fitness is accuracy), so higher fitness is better
                      higher_is_better=True,
                      elitism_rate=0.0,
                      # genetic operators sequence to be applied in each generation
                      operators_sequence=[
                          SubtreeCrossover(probability=0.8, arity=2),
                          SubtreeMutation(probability=0.1, arity=1)
                      ],
                      selection_methods=[
                          # (selection method, selection probability) tuple
                          (TournamentSelection(tournament_size=7, higher_is_better=True), 1)
                      ]
                      ),
        breeder=SimpleBreeder(),
        max_workers=1,
        max_generation=40,
        termination_checker=ThresholdFromTargetTerminationChecker(optimal=1, threshold=0.01),
        statistics=BestAverageWorstStatistics(),
        random_seed=10
    )

    # evolve the generated initial population
    algo.evolve()

    # execute the best individual after the evolution process ends
    exec1 = algo.execute(s0=0, s1=0, s2=1, d0=0, d1=0, d2=1, d3=1, d4=1, d5=0, d6=0, d7=1)
    exec3 = algo.execute(s0=0, s1=1, s2=1, d0=0, d1=0, d2=1, d3=1, d4=1, d5=0, d6=0, d7=1)
    exec7 = algo.execute(s0=1, s1=1, s2=1, d0=0, d1=0, d2=1, d3=1, d4=1, d5=0, d6=0, d7=1)
    print('execute(s0=0, s1=1, s2=1, d1=0): expected value = 0, actual value =', exec1)
    print('execute(s0=0, s1=0, s2=1, d3=1): expected value = 1, actual value =', exec3)
    print('execute(s0=1, s1=1, s2=1, d7=1): expected value = 1, actual value =', exec7)

    print('total time:', time() - start_time)


if __name__ == '__main__':
    main()
