from enum import Enum


class AlgorithmName(Enum):
    bfs = 'bfs'
    tc = 'tc'
    sssp = 'sssp'
    pr = 'pr'

    def __str__(self):
        return self.value
