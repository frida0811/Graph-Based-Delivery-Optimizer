from connector.neo4j_connector import Neo4jConnector
from graph_path_algorithm import GraphPathAlgorithm


class CaseGraphAlgorithm(GraphPathAlgorithm):
    def __init__(self):
        self._connector = Neo4jConnector(database="path")

    def create_projection(self):
        check_if_exists = """
        CALL gds.graph.exists('graph_mv')
        YIELD exists
        RETURN exists
        """
        res = self._connector.query(check_if_exists)
        self._connector.print()
        flag = res[0].get("exists")
        if not flag:
            query = """
            CALL gds.graph.project(
              'graph_mv',  ["source","transport","destination"],
              {
                convey: {properties:["cost"],orientation:"natural" }
              }
            )
            YIELD
              graphName AS graph,
              relationshipProjection AS readProjection,
              nodeCount AS nodes,
              relationshipCount AS rels
            """
            self._connector.query(query)
            self._connector.print()

    def estimate_memory_overhead_with_single_path(self, source_node, destination_node):
        query = f"""
                MATCH (s:source {{name: '{source_node}'}}), (d:destination {{name: '{destination_node}'}})
                CALL gds.shortestPath.dijkstra.write.estimate('graph_mv', {{
                    sourceNode: s,
                    targetNode: d,
                    relationshipWeightProperty: 'cost',
                    writeRelationshipType: 'convey'
                }})
                YIELD nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
                RETURN nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
                """
        self._connector.query(query)
        self._connector.print()

    def estimate_memory_overhead_with_multiple_paths(self, source_node, destination_node, k):
        query = f"""
        MATCH (s:source {{name: '{source_node}'}}), (d:destination {{name: '{destination_node}'}})
        CALL gds.shortestPath.yens.write.estimate('graph_mv', {{
            sourceNode: s,
            targetNode: d,
            k: {k},
            relationshipWeightProperty: 'cost',
            writeRelationshipType: 'convey'
        }})
        YIELD nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
        RETURN nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
        """
        self._connector.query(query)
        self._connector.print()

    def get_single_shortest_path(self, source_node, destination_node):
        query = f"""
        MATCH (s:source {{name: '{source_node}'}}), (d:destination {{name: '{destination_node}'}})
        CALL gds.shortestPath.dijkstra.stream('graph_mv', {{
            sourceNode: s,
            targetNode: d,
            relationshipWeightProperty: 'cost'
        }})
        YIELD path
        RETURN
            nodes(path) as path
        """
        self._connector.query(query)
        self._connector.print()

    def get_k_shortest_paths(self, source_node, destination_node, k):
        query = f"""
                MATCH (s:source {{name: '{source_node}'}}), (d:destination {{name: '{destination_node}'}})
                CALL gds.shortestPath.yens.stream('graph_mv', {{
                    sourceNode: s,
                    targetNode: d,
                    k: {k},
                    relationshipWeightProperty: 'cost'
                }})
                YIELD path
                RETURN
                    nodes(path) as path
                """
        self._connector.query(query)
        self._connector.print()

    def get_combined_shortest_paths(self, source, destinations: list, k):
        pass

obj = CaseGraphAlgorithm()
obj.create_projection()
obj.estimate_memory_overhead_with_single_path("drop-off point", "storage1")
obj.get_single_shortest_path("drop-off point", "storage1")
obj.estimate_memory_overhead_with_multiple_paths("drop-off point", "storage1", 2)
obj.get_k_shortest_paths("drop-off point", "storage1", 2)

