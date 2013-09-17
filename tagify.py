import sublime
import sublime_plugin
import os
import re


class TagifyCommon:
    data = {}


class Tagifier(sublime_plugin.EventListener):

    def __init__(self, *args, **kw):
        super(Tagifier, self).__init__(*args, **kw)
        self.last_sel = None

    def analyse_regions(self, view, regions):
        for region in regions:
            region = view.line(region)
            tag_region = view.find("@(?:[_a-zA-Z0-9]+)", region.a)
            if tag_region.a >= 0:
                self.tags_regions.append(tag_region)
        view.add_regions("tagify", self.tags_regions, "markup.inserted",
                         "bookmark", sublime.DRAW_NO_OUTLINE)

    def reanalyse_all(self, view):
        self.tags_regions = []
        regions = view.find_all("#@(?:[_a-zA-Z0-9]+)")
        self.analyse_regions(view, regions)

    def on_post_save_async(self, view):
        self.reanalyse_all(view)

    def on_selection_modified(self, view):
        sel = list(view.sel())
        if len(sel) != 1:
            return
        sel = sel[0]
        if self.last_sel == sel:
            return
        self.last_sel = sel
        for region in view.get_regions('tagify-link'):
            if region.contains(sel) and sel.size() > 0:
                name = view.substr(region)
                real_name = TagifyCommon.data[name]["file"]
                line_no = TagifyCommon.data[name]["line"]
                view.window().open_file(
                    "%s:%i" % (real_name, line_no), sublime.ENCODED_POSITION)
                view.sel().clear()
                return


class GenerateSummaryCommand(sublime_plugin.TextCommand):

    def run(self, edit, data):
        out = []
        cpos = 0
        regions = []
        for tag in data:
            out.append("- %s - " % tag)
            cpos += len(out[-1]) + 1
            for entry in data[tag]:
                opos = cpos
                out.append("%s" % entry["short_file"])
                cpos += len(out[-1]) + 1
                TagifyCommon.data[entry["short_file"]] = entry
                regions.append(sublime.Region(opos, cpos - 1))
            out.append("")
            cpos += 1
        self.view.insert(edit, 0, "\n".join(out))
        self.view.add_regions("tagify-link", regions)
        self.view.set_read_only(True)
        self.view.set_scratch(True)


class TagifyCommand(sublime_plugin.WindowCommand):

    def __init__(self, arg):
        super(TagifyCommand, self).__init__(arg)
        self.tag_re = re.compile("#@((?:[_a-zA-Z0-9]+))(.*?)$")

    def tagify_file(self, dirname, filename, ctags, folder_prefix):
        with open(os.path.join(dirname, filename)) as filelines:
            cpos = 0
            for n, line in enumerate(filelines):
                match = self.tag_re.search(line)
                if match:
                    path = os.path.join(dirname, filename)
                    data = {
                        'region': (cpos + match.start(1), cpos + match.end(1)),
                        'comment': match.group(2),
                        'file': path,
                        'short_file': path[len(folder_prefix)+1:],
                        'line': n + 1
                    }
                    tag_name = match.group(1)
                    if tag_name in ctags:
                        ctags[tag_name].append(data)
                    else:
                        ctags[tag_name] = [data]
                cpos += len(line)

    def run(self):
        folders = self.window.folders()
        ctags = {}
        for folder in folders:
            for dirname, dirnames, filenames in os.walk(folder):
                for filename in filenames:
                    ext = filename.split('.')[-1]
                    if ext in ('py', 'html', 'htm', 'js'):
                        self.tagify_file(dirname, filename, ctags, folder)
        summary = self.window.new_file()
        summary.set_name("Tags summary")
        summary.run_command("generate_summary", {"data": ctags})