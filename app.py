import igraph
from flask import Flask, request, jsonify, url_for
import pandas as pd
from math import inf

graphs = {}
g = None
lists = {}
dics = {}
indices = {}
pot_edges = {}
names = []
api = Flask(__name__)


@api.route('/', methods=["POST"])
def get_graph():
    json = request.get_json(force=True)
    name = json.get("name", "")
    if name == "":
        return jsonify({"success": False})
    if name in names:
        make_new = json.get("new", False)
        if make_new:
            new_graph(name)
        return jsonify({'success': True, "existed": True})
    else:
        names.append(name)
        new_graph(name)
        return jsonify({'success': True, "existed": False})


def new_graph(name):
    graphs[name] = igraph.Graph(directed=True)
    lists[name] = []
    dics[name] = {}
    indices[name] = 0
    pot_edges[name] = {}


@api.route('/add_vertex', methods=["POST"])
def add_vertex():
    json = request.get_json(force=True)
    name = json.get("name", "")
    new_vertex = json.get("vertex_name", "")
    if new_vertex in lists[name] or new_vertex == "":
        return jsonify({'success': False})
    dics[name][new_vertex] = indices[name]
    graphs[name].add_vertex(indices[name])
    indices[name] += 1
    lists[name].append(new_vertex)
    create_pot_edges(name)
    return jsonify({"success": True})


def create_pot_edges(name):
    hold = {}
    vertex_set = igraph.VertexSeq(graphs[name])
    for i in range(len(vertex_set)):
        for j in range(i + 1, len(vertex_set)):
            hold[(i, j)] = False
            hold[(j, i)] = False
    for key in pot_edges[name].keys():
        hold[key] = pot_edges[name][key]
    pot_edges[name] = hold


@api.route("/add_edge", methods=["POST"])
def add_edge():
    json = request.get_json(force=True)
    vert_from = json.get("vert_from", "")
    vert_to = json.get("vert_to", "")
    name = json.get("name", "")
    if name in graphs.keys():
        if vert_from in dics[name].keys() and vert_to in dics[name].keys():
            boolean = (dics[name][vert_from], dics[name][vert_to]) in graphs[name].get_edgelist()
            if not boolean and not causes_cycle(name, dics[name][vert_from], dics[name][vert_to]):
                graphs[name].add_edges([(dics[name][vert_from], dics[name][vert_to])])
                pot_edges[name][(vert_from, vert_to)] = True
                return jsonify({"success": True})
            if boolean:
                return jsonify({"success": False, "existed": True, "caused-cycle": False})
            else:
                return jsonify({"success": False, "caused-cycle": True, "existed": False})
        return jsonify({"success": False, "reason": "Node doesn't exist"})
    return jsonify({"success": False, "reason": "Graph doesn't exist"})


@api.route("/next_pairs", methods=["POST"])
def next_pairs():
    json = request.get_json(force=True)
    name = json.get("name", "")
    if name not in graphs.keys():
        return jsonify({"success": False, "reason": "graph doesn't exist"})
    if len(pot_edges[name].keys()) == 0 or len(pot_edges[name].keys()) == 1:
        return jsonify({"success": False, "key_1": "", "key_2": ""})
    for key in pot_edges[name].keys():
        if not pot_edges[name][key]:
            if not causes_cycle(name, key[0], key[1]):
                return jsonify({"success": True, "key_1": lists[name][key[0]], "key_2": lists[name][key[1]]})
    return jsonify({"success": False, "key_1": "", "key_2": ""})


def causes_cycle(name, i, j):
    graphs[name].add_edges([(i, j)])
    re = graphs[name].is_dag()
    graphs[name].delete_edges([(i, j)])
    if re:
        pot_edges[name][(i, j)] = True
    return not re


def fill(list_to_fill, name):
    global li
    re = []
    for element in list_to_fill:
        re.append(lists[name][element])
    return re


def get_data_frame(dic, name):
    re = {}
    i = 0
    for key in dic.keys():
        re[key] = fill(dic[key], name)
        re["Can Start {}?".format(i)] = []
        if i == 0:
            for j in range(len(dic[key])):
                re["Can Start {}?".format(i)].append("Yes")
        re["Finished {}".format(i)] = []
        i += 1
    return correct_length(re)


def correct_length(dic):
    longest = 0
    for key in dic.keys():
        if len(dic[key]) > longest:
            longest = len(dic[key])
    for key in dic.keys():
        while len(dic[key]) < longest:
            dic[key].append("")
    return dic


def make_spreadsheet(name):
    topo = topological(name)
    frame = get_data_frame(topo, name)
    writer = make_file(name)
    df = pd.DataFrame(frame)
    df.to_excel(writer, sheet_name="Sheet 1", index=False)
    formulae(writer, topo, name)
    writer.save()
    writer.close()


def make_file(name):
    return pd.ExcelWriter(url_for('static', filename="{}.xlsx".format(name)), engine='xlsxwriter')


def formulae(writer, sorted, name):
    worksheet = writer.sheets['Sheet 1']
    started = {}
    finished = {}
    for key in sorted.keys():
        for i in range(len(sorted[key])):
            started[sorted[key][i]] = chr(ord('A') + 3 * int(key) + 1) + str(i + 2)
            finished[sorted[key][i]] = chr(ord('A') + 3 * int(key) + 2) + str(int(i) + 2)
    for key in sorted.keys():
        for i in range(len(sorted[key])):
            if_statement = '=IF({0},"Yes", "")'.format(ands(sorted[key][i], finished, name))
            worksheet.write(started[sorted[key][i]], if_statement)


def ands(element, finished, name):
    li = graphs[name].predecessors(element)
    string = ""
    for i in range(len(li)):
        if i != 0:
            string += ","
        hold = finished[li[i]] + '<>""'
        string += hold
    if len(li) == 0:
        string = "True"
    elif len(li) > 1:
        string = "And(" + string + ")"
    return string


def topological(name):
    search = graphs[name].topological_sorting()
    shortest_paths = graphs[name].shortest_paths()
    order = 0
    re = {}
    li = [search[0]]
    for current in range(1, len(search)):
        same_level = True
        for element in li:
            if same_level and shortest_paths[element][search[current]] != inf:
                same_level = False
        if same_level:
            li.append(search[current])
        else:
            re[order] = li
            li = [search[current]]
            order += 1
    re[order] = li
    return re


@api.route("/get_spreadsheet", methods=["GET", "POST"])
def get_spreadsheet():
    json = request.get_json(force=True)
    name = json.get("name", "")
    if name not in graphs.keys():
        return jsonify({"success": False, "reason": "graph doesn't exist"})
    make_spreadsheet(name)
    return api.send_static_file("{}.xlsx".format(name))


if __name__ == "__main__":
    api.run()
