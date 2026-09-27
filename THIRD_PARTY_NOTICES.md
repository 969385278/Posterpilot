# Third-party materials

## Fonts

The six unmodified title fonts under `data/fonts/open-source/` originate from Google Fonts and use the SIL Open Font License 1.1. Each font directory retains its `OFL.txt` copyright and license notice and upstream `METADATA.pb`. The manifest records source URLs, upstream revision and hashes. See [font documentation](data/fonts/open-source/README.md).

Windows system fonts are referenced on a Windows development machine; their files are not distributed here.

## Reference posters

Reference images in `data/knowledge/cases/images/` are accompanied by Wikimedia Commons metadata snapshots under `sources/`. Licenses vary: most selected works are marked `Public domain`, while the [Wikimania 2022 poster](https://commons.wikimedia.org/w/index.php?curid=122316577) is by Katie Crampton (WMUK) under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Its image content is unmodified; author, source and license links are retained in the catalog and UI. The excluded [wikiArS workshop photo](https://commons.wikimedia.org/w/index.php?curid=31973814) is by Dvdgmz under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); the source thumbnail is retained unmodified along with its attribution metadata. Do not assume a common license for all images. See [case documentation](data/knowledge/cases/README.md) and the per-file metadata. These records are not a guarantee for every jurisdiction or every trademark use.

## Rendering demonstration backgrounds

`data/media/` contains public-domain-source artwork and photography with per-file metadata and hashes. The six images in `apps/web/public/showcase/` are deterministic rendering demonstrations using those backgrounds and the bundled OFL fonts, not outputs of an image-generation model. They include cropping, background treatment and fictional event text. Attribution and transformations are documented in [the media README](data/media/README.md) and the public showcase manifest. Failed readability checks remain disclosed; these assets do not prove user acceptance or model-quality improvement.

## Design knowledge

The repository includes short, structured design-rule summaries with links to DENSO WAVE, W3C and Nielsen Norman Group, plus separately marked internal candidate rules. Original publications remain subject to their source organizations' terms. Original local PDF files and extracted PDF text are excluded; redistribution permission for those files is not assumed.

## Models and libraries

Python/npm dependencies retain their upstream licenses. DeepGaze, CLIP, PyTorch and downloaded model weights must be used under their respective licenses and terms; weights are not included here. Commercial model APIs require the user's own account and access.

## Project code

Public visibility is not itself a grant of an MIT/Apache or other broad project license. No repository-wide license has been selected in this publication pass. Third-party licenses apply to their own materials, not automatically to the complete project.
