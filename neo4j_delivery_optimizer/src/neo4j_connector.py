from py2neo import Graph
import json
from prettytable import PrettyTable, ALL


class Neo4jConnector:
    def __init__(self, database):
        self.result = None
        self.connector = Graph("bolt://localhost:7687", auth=("neo4j", "12345678"), name=database)

    def query(self, query):
        self.result = self.connector.run(query).data()
        return self.result

    def print(self):
        if not self.result:
            return
        print(json.dumps(self.result, indent=2))

    def print_shortest_paths(self):
        if not self.result:
            return
        table = PrettyTable(['index', 'path', 'total_cost'])
        table.hrules = ALL
        table.align["path"] = "l"
        table._max_width = {'index': 10, 'source_node': 10, 'destination_node': 10, 'path': 100, 'total_cost': 10}
        idx = 1

        for path_info in self.result:
            path = path_info.get('path')
            total_cost = path_info.get('totalCost')
            table.add_row([idx, '->'.join([_.get('name') for _ in path]), total_cost])
            idx += 1
        print(table)

    def print_combined_shortest_paths(self, format_subpath=False):
        if not self.result:
            return

        def find_overlaps(path_a, path_b):
            tmp = {}
            idx_a = 0
            while idx_a < len(path_a):
                idx = 0
                start = idx_a
                end = idx_a
                for idx_b in range(len(path_b)):
                    if path_a[end] == path_b[idx_b]:
                        end += 1
                        idx_b += 1
                        idx += 1
                    else:
                        idx = 0
                        start = end
                        continue
                    if idx > 1:
                        tmp[start] = end

                idx_a += 1

            res = {}
            for key, val in tmp.items():
                if val not in res.keys():
                    res[val] = key
                else:
                    pre_key = res[val]
                    if pre_key > key:
                        res[val] = key
            return res

        table = PrettyTable(['index', 'path', 'total_cost'])
        table.hrules = ALL
        table.align["path"] = "l"
        table._max_width = {'index': 10, 'path': 500, 'total_cost': 10}
        idx = 1

        for path_info in self.result:
            paths = []
            costs = []
            total_cost = 0
            for key, val in path_info.items():
                if key.startswith('p'):
                    paths.append(val)
                    continue
                if key.startswith('c_'):
                    total_cost = val
                else:
                    costs.append(val)

            # only can format 2 destinations

            if format_subpath:

                path1, path2 = paths
                overlapped_part_path1 = find_overlaps(path1, path2)
                overlapped_part_path2 = find_overlaps(path2, path1)

                def format_subpath(path, overlapped_part_path):
                    s = ""
                    for _ in range(len(path)):
                        flag = False
                        arrow_flag = False
                        for end, start in overlapped_part_path.items():
                            if start <= _ < end:
                                flag = True
                                if _ == (end - 1):
                                    arrow_flag = False
                                else:
                                    arrow_flag = True
                                break
                        if flag:
                            s += "\033[33m%s\033[0m" % f"{path[_]}->" if arrow_flag else "\033[33m%s\033[0m" % f"{path[_]}" + "->"
                        else:
                            s += f"{path[_]}->"
                    return s[:-2]
                paths = [format_subpath(path1, overlapped_part_path1), format_subpath(path2, overlapped_part_path2)]

            paths = '\n'.join([(paths[_] if format_subpath else "->".join(paths[_])) +
                               "\033[1;32m%s\033[0m" % "  (cost: {cost})".format(cost=costs[_]) for _ in
                               range(len(paths))])
            table.add_row([idx, paths, "\033[1;34m%s\033[0m" % total_cost])
            idx += 1
        print(table)