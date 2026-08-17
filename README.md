# Cheetah connectivity project

Manuscript, predeclared protocol, and analysis code for a study of temporal
structural connectivity, unprotected pinch points, and monitoring priorities for
free-ranging cheetahs in southern Africa.

## Layout

    tex/          manuscript (main.tex + sections/)
    protocol/     predeclared analysis protocol
    refs/         bibliography (methods_canon.bib verified; cheetah_lit.bib from Zotero)
    figures/      figure inputs, PDF preferred over PNG
    tables/       generated tables
    tools/        flatten.py builds the single-file paste version
    .github/      CI: builds both PDFs on every push

## Building

    make            # both PDFs
    make watch      # continuous rebuild while writing
    make clean

Requires TeX Live with biblatex-apa and biber. Or open the repo in a GitHub
Codespace and the devcontainer supplies both.

## Protocol lock

The protocol is fixed before any connectivity result is generated. When it is
signed, tag it:

    git tag -a protocol-v1.0 -m "protocol locked, advisor signed"
    git push origin protocol-v1.0

Amendments after that point go in the protocol's amendment log AND get their own
commit, so the sequence of changes is externally checkable.

## What must never be committed

Spatial inputs. Occurrence data is sensitive and WDPA cannot be redistributed
under its licence. See .gitignore. Code and derived summaries only.
