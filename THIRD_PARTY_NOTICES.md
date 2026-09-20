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

## AI-generated concept artwork

`docs/demo/assets/calligraphy-photography-concept.png` was generated directly with Codex's built-in image generation tool for this repository's visual concept section. It is not a PosterPilot workflow output, benchmark, or before/after optimization result. Its calligraphy is part of the generated raster image, not an extracted or bundled font. The club, date and venue are fictional demonstration information. The generation prompt is preserved in [the concept notes](docs/demo/calligraphy-photography-prompt.md). No third-party reference image was supplied for this concept.

`docs/demo/assets/menghonglou-concept-initial.png` and `menghonglou-concept-optimized.png` show an AI-generated design and a subsequent image edit guided by human-specified layout changes, both made with Codex's built-in image generation tool. They are not PosterPilot Agent outputs or measured optimization results. The initial concept used no external reference image; the edit used that generated initial image. Their calligraphy is raster artwork, not redistributed font software, and the event details are fictional. Prompts and limitations are recorded in [the iteration notes](docs/demo/menghonglou-concept-iteration.md).

`docs/demo/assets/menghonglou-oil-initial.png` and `menghonglou-oil-optimized.png` are a subsequent portrait-focused oil-painting redesign and typography refinement made with Codex's built-in image generation tool. The first used the previously generated `menghonglou-concept-initial.png` as its edit input; the second used `menghonglou-oil-initial.png`. No new third-party reference image was added. These are AI visual concepts, not PosterPilot workflow or evaluation outputs. Their event facts are fictional, and the calligraphy and oil texture are generated raster artwork rather than font software. See [the oil portrait notes](docs/demo/menghonglou-oil-iteration.md) for the actual edit prompts and provenance.

`docs/demo/assets/menghonglou-ink-initial.png` and `menghonglou-ink-optimized.png` were made with Codex's built-in image generation tool. The initial poster used a user-supplied image as a style reference; the second used only that generated poster as an edit input. The reference image's author, source and license have not been verified; the reference file is not included in this repository and is not presumed public domain. These generated illustrations are not PosterPilot workflow or evaluation outputs. Event details are fictional; calligraphic text is raster artwork, not font software. See [the ink-painting notes](docs/demo/menghonglou-ink-iteration.md) for prompts and provenance limitations.

## Project code

Public visibility is not itself a grant of an MIT/Apache or other broad project license. No repository-wide license has been selected in this publication pass. Third-party licenses apply to their own materials, not automatically to the complete project.
