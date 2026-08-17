import re, pathlib

tex = pathlib.Path("/root/cheetah/tex")
refs = pathlib.Path("/root/cheetah/refs")
main = (tex / "main.tex").read_text()

bib = (refs / "methods_canon.bib").read_text()

header = r"""%##############################################################################
%  SINGLE-FILE VERSION -- everything below is one self-contained document.
%
%  Save as main.tex and build with:   latexmk -pdf main.tex
%  Needs TeX Live with biblatex-apa and biber. On Overleaf, set the
%  bibliography tool to Biber in Menu > Settings (it defaults to BibTeX).
%
%  The two filecontents blocks below write refs/methods_canon.bib and an empty
%  refs/cheetah_lit.bib on the first compile, so you do not need to create any
%  other file. Export your Literature sheet from Zotero into cheetah_lit.bib
%  once you have it, then delete that second filecontents block so your export
%  stops being overwritten on every build.
%
%  Section boundaries are marked with  % ===== SECTION: name  so you can split
%  this back into separate files later if it gets unwieldy. It will.
%##############################################################################

"""

# emit the bib via filecontents
fc = "\\begin{filecontents*}[overwrite]{methods_canon.bib}\n" + bib + "\\end{filecontents*}\n\n"
fc += ("\\begin{filecontents*}[overwrite]{cheetah_lit.bib}\n"
       "% Export your Literature sheet here from Zotero (Better BibTeX recommended).\n"
       "% Delete this filecontents block once you do, or every build will wipe it.\n"
       "\\end{filecontents*}\n\n")


def expand(m):
    name = m.group(1)
    body = (tex / (name + ".tex")).read_text().rstrip()
    bar = "=" * 60
    return ("% ===== SECTION: {0} {1}\n{2}\n% ===== end {0}\n".format(name, bar, body))


out = re.sub(r"\\input\{(sections/[^}]+)\}", expand, main)
# single-file layout is flat: main.tex sits beside refs/ and figures/, not below them
out = out.replace("{../refs/", "{").replace("{{../figures/}}", "{{figures/}}")
out = header + fc + out
pathlib.Path("/root/cheetah/cheetah_manuscript_single_file.tex").write_text(out)
print(len(out.splitlines()), "lines")
