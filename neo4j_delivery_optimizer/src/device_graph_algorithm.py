from connector.neo4j_connector import Neo4jConnector
from graph_path_algorithm import GraphPathAlgorithm


class DeviceGraphAlgorithm(GraphPathAlgorithm):

    def __init__(self):
        self._connector = Neo4jConnector(database="device")

    def create_projection(self):
        check_if_exists = """
        CALL gds.graph.exists('graph_mv')
        YIELD exists
        RETURN exists
        """
        res = self._connector.query(check_if_exists)
        self._connector.print()
        flag = res[0].get("exists")
        if flag:
            drop_existed_projection = """
            CALL gds.graph.drop('graph_mv') 
            YIELD graphName;
            """
            self._connector.query(drop_existed_projection)
            self._connector.print()
        query = """
                    CALL gds.graph.project(
                      'graph_mv',  ["source","transport","destination"],
                      {
                        convey: {properties:["totalCost"],orientation:"natural" }
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
                    relationshipWeightProperty: 'totalCost',
                    writeRelationshipType: 'convey'
                }})
                YIELD nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
                RETURN nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
                """
        self._connector.query(query)
        #self._connector.print()

    def estimate_memory_overhead_with_multiple_paths(self, source_node, destination_node, k):
        query = f"""
        MATCH (s:source {{name: '{source_node}'}}), (d:destination {{name: '{destination_node}'}})
        CALL gds.shortestPath.yens.write.estimate('graph_mv', {{
            sourceNode: s,
            targetNode: d,
            k: {k},
            relationshipWeightProperty: 'totalCost',
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
            relationshipWeightProperty: 'totalCost'
        }})
        YIELD index, path, totalCost
        WHERE NONE(n IN nodes(path) WHERE n.state <> 'idle')
        RETURN
            nodes(path) as path, totalCost
        """
        self._connector.query(query)
        self._connector.print()

    def get_k_shortest_paths(self, source, destination_nodes: list, k):
        query = """
CALL {{
{subqueries_clause}
}}
RETURN sourceNode, targetNode, totalCost, path
ORDER BY totalCost
LIMIT {k};"""
        subquery_template = """MATCH (s:source {{name: '{source}'}}), (d:destination {{name: '{destination}'}})
CALL gds.shortestPath.yens.stream('graph_mv', {{
    sourceNode: s,
    targetNode: d,
    k: {k},
    relationshipWeightProperty: 'totalCost'
}})
YIELD sourceNode, targetNode, totalCost, path
WHERE NONE(n IN nodes(path) WHERE n.state <> 'idle')
RETURN sourceNode, targetNode, totalCost, nodes(path) as path"""
        subqueries = [subquery_template.format(source=source, destination=_, k=k) for _ in destination_nodes]
        exec_query = query.format(subqueries_clause='\nUNION ALL\n'.join(subqueries), k=k)
        print(f"executing query ->{exec_query}")
        self._connector.query(exec_query)
        self._connector.print_shortest_paths()

    def get_combined_shortest_paths(self, source, destinations: list, k):
        match_clause_template = \
            """match p{idx}=(s:source{{name:'{source}'}})-[*]->(d{idx}:destination {{name:'{destination}'}})"""
        match_clauses = [match_clause_template.format(idx=_, source=source,
                                                     destination=destinations[_]) for _ in range(len(destinations))]
        filter_clause_template = """NONE(n IN nodes(p{idx}) WHERE n.state <> 'idle')"""
        filter_clauses = [filter_clause_template.format(idx=_) for _ in range(len(destinations))]

        name_filter_clause_template = """[node in nodes(p{idx}) | node.name] as p{idx}"""
        name_filter_clauses = [name_filter_clause_template.format(idx=_) for _ in range(len(destinations))]

        reduce_cost_clause_template = \
            """reduce(cost = 0, rel in relationships(p{idx}) | cost + rel.totalCost) AS c{idx}"""
        reduce_cost_clauses = [reduce_cost_clause_template.format(idx=_) for _ in range(len(destinations))]

        collect_total_cost_clause_template = """collect(p{idx})"""
        collect_total_cost_clause = '+'.join([collect_total_cost_clause_template.format(idx=_)
                                              for _ in range(len(destinations))]) + ' as p_total'

        min_aggregation_clause_template = """p{idx}, min(c{idx}) as c{idx}"""
        min_aggregation_clauses =  [min_aggregation_clause_template.format(idx=_) for _ in range(len(destinations))]

        return_clause_template = """p{idx}, c{idx}"""
        return_clause = ' ,'.join([return_clause_template.format(idx=_) for _ in range(len(destinations))])

        query = """
{match_clauses}
where
{filter_clauses}
with
{name_filter_clauses},
{reduce_cost_clauses},
{collect_total_cost_clause}
with 
{min_aggregation_clauses},
reduce(combinedPath = [], path in p_total |
  combinedPath + nodes(path) + relationships(path)
) as mergedPath
with
{min_aggregation_clauses},
reduce(uniqueItems = [], item in mergedPath |
case when not item in uniqueItems then uniqueItems + [item] else uniqueItems end
) AS deduplicatedmergedPath  
return {return_clause}, reduce(cost = 0, p in deduplicatedmergedPath | cost + p.cost) as c_total
order by c_total
limit {k}"""
        exec_query = query.format(
            match_clauses='\n'.join(match_clauses),
            filter_clauses=' and \n'.join(filter_clauses),
            name_filter_clauses=', \n'.join(name_filter_clauses),
            reduce_cost_clauses=', \n'.join(reduce_cost_clauses),
            collect_total_cost_clause=collect_total_cost_clause,
            min_aggregation_clauses=', \n'.join(min_aggregation_clauses),
            return_clause=return_clause,
            k=k
        )
        print(exec_query)
        self._connector.query(exec_query)
        self._connector.print_combined_shortest_paths(format_subpath=len(destinations)==2)


obj = DeviceGraphAlgorithm()
# obj.create_projection()
# obj.estimate_memory_overhead_with_single_path("SOURCE_1", "DEST1")
# obj.get_single_shortest_path("SOURCE_1", "DEST1")
# obj.estimate_memory_overhead_with_multiple_paths("SOURCE_1", "DEST1", 5)
# obj.get_k_shortest_paths("SOURCE_1", ['DEST5','DEST10','DEST_LOAD','DEST_CLEAN'], 50)
# obj.get_combined_shortest_paths('SOURCE_1', ['DEST4', 'DEST5', 'DEST6', 'DEST11', 'DEST_LOAD'], 5)
obj.get_combined_shortest_paths('SOURCE_1', ['DEST4', 'DEST6'], 25)
