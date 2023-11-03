
import argparse
import graphviz

import pprint
import re



patternModule = re.compile(r"module\s+(?P<name>\w+)(?P<params>\s*#\([^\)]*\))?\s*\((?P<args>[^\)]*)\)\s*;(?P<data>[\s\S]*?(?=endmodule))endmodule")
patternParam = re.compile(r"parameter(?P<type>\s+[a-zA-Z]+)?(?P<size>\s*\[.*\])?(?P<name>\s+\w+)\s*(?P<default>=.*)")
patternArg = re.compile(r"(?P<dir>output|input|inout)?(?P<type>\s+reg|wire)?(?P<size>\s\[[^\]]*\])?(?P<name>\s\w+)")

parser = argparse.ArgumentParser()
parser.add_argument('verilog', type=str, nargs='+')
parser.add_argument("--output", "-o", help="output directory", type=str, default=None)
parser.add_argument("--top", "-t", help="top module", type=str, default="top")
sargs = parser.parse_args()


modules = {}
for verilog_file in sargs.verilog:
    verilogData = open(verilog_file, "r").read()
    verilogData = re.sub(r"//.*", "", verilogData)
    verilogData = re.sub(r"/\*.*\*/", "", verilogData)

    for result in patternModule.finditer(verilogData):
        moduleName = result.group("name")
        moduleData = result.group("data")
        modules[moduleName] = {
            "filename": verilog_file,
            "args": {},
            "params": {},
            "data": moduleData,
            "sub": [],
        }
        
        defines = []
        
        moduleArgs = []
        moduleArgLast = {}
        
        args = []
        for arg in result.group("args").split("\n"):
            #print(arg)
            if arg.startswith("`"):
                args.append(f"{arg},")
            else:
                args.append(arg)

        for arg in ' '.join(args).split(","):
            moduleArg = {}
            if not arg:
                continue

            arg = re.sub(r"\s+", " ", arg.strip())
            
            if arg.startswith("`"):
                if arg.startswith("`ifndef"):
                    defines.append(arg)
                elif arg.startswith("`ifdef"):
                    defines.append(arg)
                elif arg.startswith("`endif"):
                    defines.pop()
            else:

                moduleArg["defines"] = defines.copy()

                argm = patternArg.search(arg)
                if argm:
                    if argm["dir"]:
                        moduleArg["direction"] = argm["dir"]
                    if argm["type"]:
                        moduleArg["type"] = argm["type"]
                    if argm["size"]:
                        moduleArg["size"] = argm["size"]
                    if argm["name"]:
                        moduleArg["name"] = argm["name"]
                    modules[moduleName]["args"][moduleArg["name"]] = moduleArg
                    moduleArgLast = moduleArg
                elif len(arg.strip().split()) == 1:
                    moduleArg = moduleArgLast.copy()
                    moduleArg["name"] = arg.strip()
                    modules[moduleName]["args"][moduleArg["name"]] = moduleArg
                else:
                    print(f"UNKNOWN ARG ({moduleName}): {arg.strip()} <br/>")

        if result.group("params"):
            for arg in result.group("params").strip().lstrip("#").lstrip("(").rstrip(")").split(","):
                param = patternParam.search(arg.strip())
                if param:
                    moduleParam = {}
                    moduleParam["name"] = param["name"].strip()
                    if param["type"]:
                        moduleParam["size"] = param["type"].strip().replace(" ", "")
                    if param["size"]:
                        moduleParam["size"] = param["size"].strip().replace(" ", "")
                    if param["default"]:
                        moduleParam["default"] = param["default"].strip().lstrip("=").strip().replace(" ", "").replace("_", "")

                    modules[moduleName]["params"][moduleParam["name"]] = moduleParam
                else:
                    print(f"UNKNOWN PARAMETER ({moduleName}): {arg.strip()} <br/>")


        data = re.sub(r"`(if|else|end|def).*", "", result.group("data"))
        for arg in data.split(";"):
            param = patternParam.search(arg.strip())
            if param:
                moduleParam = {}
                moduleParam["name"] = param["name"].strip()
                if param["type"]:
                    moduleParam["size"] = param["type"].strip().replace(" ", "")
                if param["size"]:
                    moduleParam["size"] = param["size"].strip().replace(" ", "")
                if param["default"]:
                    moduleParam["default"] = param["default"].strip().lstrip("=").strip().replace(" ", "").replace("_", "")

                modules[moduleName]["params"][moduleParam["name"]] = moduleParam
            else:

                known = {
                    "if",
                    "reg",
                    "wire",
                    "always",
                    "end",
                    "assign",
                    "localparam",
                    "initial",
                    "generate",
                    "case",
                    "else",
                    "endcase",
                    "`assert",
                    "",
                    "(*",
                    "{",
                }
                arg = arg.strip()
                splitted = arg.split()
                if arg and "(" in arg and splitted[0] not in known and len(splitted) > 2 and splitted[1] != "=" and splitted[1] != "<=":
                    modules[moduleName]["sub"].append([splitted[0], arg])



if sargs.top not in modules:
    
    if "rio" in modules:
        sargs.top = "rio"
        print(f"FALLBACK: setting top module to '{sargs.top}'")
    elif "top" in modules:
        sargs.top = "top"
        print(f"FALLBACK: setting top module to '{sargs.top}'")
    else:
        print(f"ERROR: top '{sargs.top}' module not found")
        print(f"Modules: {', '.join(modules.keys())}")
        exit(1)


if sargs.output is None:
    if "/" in modules[sargs.top]["filename"]:
        sargs.output = "/".join(modules[sargs.top]["filename"].split("/")[0:-1])
    else:
        sargs.output = "./"

    print(f"setting output directory to {sargs.output}")



def mexpand(dependsGraph, module):
    dependsGraph[module] = {}
    for sub in modules[module]["sub"]:
        if sub[0] in modules:
            mexpand(dependsGraph[module], sub[0])
    return dependsGraph


def dependsGraph2menu(fd, dependsGraph, prefix=""):
    for module in dependsGraph:
        filename = modules[module]["filename"]
        fd.write(f"{prefix}<a target='main' href='{filename.split('/')[-1]}.html#{module}'>{module}</a><br/>\n")
        dependsGraph2menu(fd, dependsGraph[module], prefix + "|&nbsp;")



dependsGraph = mexpand({}, sargs.top)

filename = modules[sargs.top]["filename"]
fd = open(f"{sargs.output}/index.html", "w")
fd.write("<html>")
fd.write("  <frameset cols=\"200, *\">")
fd.write("    <frame src=\"menu.html\" name=\"menu\">")
fd.write(f"    <frame src=\"{filename.split('/')[-1]}.html\" name=\"main\">")
fd.write("  </frameset>")
fd.write("</html>")
fd.close()


fd = open(f"{sargs.output}/menu.html", "w")
dependsGraph2menu(fd, dependsGraph)
fd.close()



output = "html"

if output == "markdown":
    for moduleName, module in modules.items():
        print(f"# {moduleName}")
        print("")

        print("## arguments")
        print("")
        print("| direction | type | size | name |")
        print("| --- | --- | --- | --- |")
        for argName, arg in module["args"].items():
            print(f"| {arg.get('direction', '')} | {arg.get('type', '')} | {arg.get('size', '')} | {argName} | {arg.get('defines') or ''} |")
        print("")

        if module["params"]:
            print("## parameter")
            print("")
            print("| size | name | default |")
            print("| --- | --- | --- |")
            for argName, arg in module["params"].items():
                print(f"| {arg.get('size', '')} | {arg.get('name', '')} | {arg.get('default', '')} |")
            print("")

else:

    gAll = graphviz.Digraph('G', format="svg")
    gAll.attr(rankdir='LR')


    for verilog_file in sargs.verilog:

        fd = open(f"{sargs.output}/{verilog_file.split('/')[-1]}.html", "w")

        fd.write("""
<style>
table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}
</style>

    """)

        fd.write(f"<h1>{verilog_file.split('/')[-1]}</h1>\n")

        for moduleName, module in modules.items():

            if module["filename"] != verilog_file:
                continue

            fd.write(f"<h2 id='{moduleName}'>{moduleName}</h2>\n")
            fd.write(f"<hr/>\n")

            fd.write("<h3>flow</h3>\n")
            gSub = graphviz.Digraph('G', format="svg")
            gSub.attr(rankdir='LR')
            gSub.node(moduleName, shape='box', label=moduleName)
            for moduleNameFrom, moduleFrom in modules.items():
                for subFrom in moduleFrom["sub"]:
                    if subFrom[0] == moduleName:
                        gSub.edge(moduleNameFrom, moduleName)
                        filename = modules[moduleNameFrom]["filename"]
                        gSub.node(moduleNameFrom, shape='plaintext', label=moduleNameFrom, href=f"{filename.split('/')[-1]}.html#{moduleNameFrom}")
            for sub in module["sub"]:
                if sub[0] in modules:
                    gAll.edge(moduleName, sub[0])
                    filename = modules[sub[0]]["filename"]
                    gSub.node(sub[0], shape='plaintext', label=sub[0], href=f"{filename.split('/')[-1]}.html#{sub[0]}")
                    gSub.edge(moduleName, sub[0])
            fd.write(gSub.pipe().decode())
            fd.write("\n")
            fd.write("<br>\n")


            filename = modules[moduleName]["filename"]
            gAll.node(moduleName, shape='plaintext', label=moduleName, href=f"{filename.split('/')[-1]}.html#{moduleName}")


            fd.write("<h3>arguments</h3>\n")
            fd.write("<table>\n")
            fd.write("<tr><th>direction</th><th>type</th><th>size</th><th>name</th></tr>\n")
            for argName, arg in module["args"].items():
                fd.write(f"<tr><td>{arg.get('direction', '')}</td><td>{arg.get('type', '')}</td><td>{arg.get('size', '')}</td><td>{argName}</td><td>{arg.get('defines') or ''}</td></tr>\n")
            fd.write("</table>\n")
            fd.write("<br>\n")

            if module["params"]:
                fd.write("<h3>parameter</h3>\n")
                fd.write("<table>\n")
                fd.write("<tr><th>size</th><th>name</th><th>default</th></tr>\n")
                for argName, arg in module["params"].items():
                    fd.write(f"<tr><td>{arg.get('size', '')}</td><td>{arg.get('name', '')}</td><td>{arg.get('default', '')}</td></tr>\n")
                fd.write("</table>\n")
                fd.write("<br>\n")


            #if module["sub"]:
                #fd.write("<h3>sub modules</h3>")
                #fd.write("<table>")
                #fd.write("<tr><th>module</th><th>source</th></tr>")
                #for sub in module["sub"]:
                #    if sub[0] in modules:
                #        fd.write(f"<tr><td><a href='#{sub[0]}'>{sub[0]}</a></td><td><pre>{sub[1]}</pre></td></tr>")
                #fd.write("</table>")



            fd.write("<pre>")
            fd.write(module["data"])
            fd.write("</pre>")
            
        fd.close()


    #print("<hr/>")
    #print(gAll.pipe().decode())










