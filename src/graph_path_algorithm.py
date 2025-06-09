from abc import ABCMeta, abstractmethod
from typing import Union


class GraphPathAlgorithm(metaclass=ABCMeta):
    @abstractmethod
    def create_projection(self):
        pass

    @abstractmethod
    def estimate_memory_overhead_with_single_path(self, source_node, destination_node):
        pass

    @abstractmethod
    def estimate_memory_overhead_with_multiple_paths(self, source_node, destination_node, k):
        pass

    @abstractmethod
    def get_single_shortest_path(self, source_node, destination_node):
        pass

    @abstractmethod
    def get_k_shortest_paths(self, source_node, destination: Union[str, list] , k):
        pass

    @abstractmethod
    def get_combined_shortest_paths(self, source, destinations: list, k):
        pass
