# Space Apps 2026 submission: Guardians of the Harvest

Draft answers for the project form (Space Apps → Team → **Project** tab). Copy and paste them,
then adjust. **Deadline: Sunday, November 15, 2026, 11:59 PM local time of our Local Event.**
Only the last click on **Submit for Judging** counts, and nothing can be edited after the deadline.

## Checklist

| # | Field | Required | Status | Owner |
|---|---|---|---|---|
| 1 | Project Name | yes | ✅ "Guardians of the Harvest" | — |
| 2 | Summary (≤ 1,500 characters) | yes | ✏️ Draft below | Andres |
| 3 | Project Demonstration (public link) | yes | ❌ **Missing:** a video **≤ 30 s** *or* slides **≤ 7** (title included) | a teammate (name TBD) |
| 4 | Project (public link) | yes | ✅ https://terracosmos.space (the repo is public too, see below) | — |
| 5 | Project Details | yes | ✏️ Draft below | Andres |
| 6 | Use of Super Intelligence (SI) | yes | ✅ Code only (team decision, 2026-11-15) | Andres |
| 7 | NASA Data (links) | yes | ✅ List below | — |
| 8 | Space Agency Partner & Other Data | no, but expected | ✅ List below | — |
| 9 | Terms and Conditions + Original work | yes | ✅ Already checked in the form | — |
| 10 | **Submit for Judging** | yes | ❌ Click after everything above, **before 11:59 PM** | Andres |

Tips from the form: use **Lock** while editing so two people don't overwrite each other, and
**Save Progress** often. Saving doesn't submit.

### Links must work without a login

- **The repo is now PUBLIC** (checked on 2026-11-15): judges can open
  https://github.com/saenzj2/HackatonPrep. The Project link is still https://terracosmos.space
  (`/docs` shows the API). Mention the repo link in Project Details if you want. The history never
  contained `.env` files or API keys, and a test checks that the data snapshot has none.
- Demo: YouTube (Public or Unlisted), Google Drive or GitHub with "anyone with the link can view".
  Open it in a private window before you paste it.
- Paste full URLs, starting with `https://`.

### Before you click Submit

- [ ] https://terracosmos.space/app/ loads, and "Comparar rotaciones" returns results for San Carlos and Alajuela.
- [ ] The demo link opens in a private window. The video is ≤ 30 s, or the deck has ≤ 7 slides.
- [ ] Any SI-generated image or video has a **visible watermark** ("AI-generated").
- [ ] No NASA logos, flags or mission identifiers in anything we made, especially SI-generated content.
- [ ] Every resource we used is in the NASA Data or Other Data lists.

---

## 2. Summary (paste as is: 161 words, 1,136 characters)

> Guardians of the Harvest helps smallholder farmers compare crop rotation options using NASA Earth
> observation data. A farmer picks a field location, the crops they can grow, their current rotation
> and what matters most to them (water, soil or climate). The tool then ranks two-season rotations
> (Costa Rica's "primera" and "postrera" rainy seasons) for that field.
>
> Each crop is scored against the field's real conditions: NASA POWER climate (temperature, heat and
> frost stress, rainfall), NASA SMAP root-zone soil moisture and waterlogging risk, and OpenLandMap
> soil pH. Crop tolerance ranges come from FAO EcoCrop. Rotation rules reward breaking pest cycles
> and adding legumes, and penalize monoculture. Every recommendation explains its benefits, its risks,
> the data behind it and what the data can't see, in English and Spanish.
>
> The challenge asks for decision support that adapts farms to changing temperature, rain and
> extremes. Our answer turns global satellite and model data into one clear, explainable
> recommendation per field, compared against what the farmer does today, so farmers can test
> resilient alternatives before risking a season.

## 3. Project Demonstration

**Missing.** Choose one:
- **Video ≤ 30 s:** screen recording of https://terracosmos.space/app/: pick San Carlos → compare
  rotations → show the ranking and one explanation in Spanish. Add a title card and voice-over or captions.
- **Slides ≤ 7:** (1) title + team, (2) problem, (3) how it works (data flow), (4) NASA data used,
  (5) demo screenshot (San Carlos ranking), (6) impact + limits, (7) next steps + link.

Upload, set it to public or "anyone with the link", and paste the full URL.

## 4. Project link

https://terracosmos.space

## 5. Project Details (paste and adjust)

> **What it does.** Guardians of the Harvest is a decision-support web app and API that compares
> crop rotation strategies for a specific field. Input: a location, candidate crops, the farmer's
> current rotation and priorities (water, soil, climate). Output: a ranked list of rotations with a
> 0–1 suitability score, a breakdown by category, and plain-language benefits, risks, data gaps and
> evidence, in English and Spanish. A second endpoint suggests the best sowing months per crop.
>
> **How it works.** For each crop and season we score how well the field's conditions fit the crop's
> tolerance ranges (FAO EcoCrop): monthly temperature, heat-stress and frost-risk days from NASA
> POWER daily max/min temperature, rainfall and dry-month checks from NASA POWER precipitation,
> root-zone soil moisture and waterlogging from NASA SMAP L4, and soil pH from OpenLandMap. Scores are
> weighted by the farmer's priorities. Rotation rules then reward legumes and family changes and
> penalize monoculture and pest carry-over. The farmer's current rotation is always scored as the
> baseline, so every alternative shows how much it improves on what they do today.
>
> **Benefits and impact.** Smallholders rarely get field-specific advice on how climate change
> affects their rotations. We turn global, free NASA data into one explainable recommendation,
> honest about uncertainty: every result lists what the satellite data cannot see (drainage, slope,
> local pests, markets) so farmers and extension agents check locally before acting.
>
> **Pilot scope.** Costa Rica (San Carlos and Alajuela demo fields), maize, beans and rice plus
> cowpea and sorghum, with the two rainfed seasons (primera May–Aug, postrera Sep–Nov). Region,
> crops, variables and weights are configuration, not code, so the tool can be extended.
>
> **Tools.** Python 3.12, FastAPI, Pydantic, pandas, httpx, Google Earth Engine API, an OpenAPI
> contract, pytest (600+ tests), ruff and mypy, HTML/CSS/JavaScript, Docker, GitHub Actions, Railway
> hosting and Cloudflare DNS.
>
> **Creativity and factors considered.** We prioritized explainability and honesty over a black-box
> score: each number is traceable to its NASA source. The demo runs from cached real data so it
> works offline and reproducibly. Farmer-facing texts use Costa Rican Spanish terms. The agronomic
> rules were reviewed for soundness, and data sources and units are documented for every input.

## 6. Use of Super Intelligence (SI)

Team decision (2026-11-15): declared **Code** only. **Updated the same day:** the web app and the
presentation now include AI-generated media and text, so the form should also select **Text**,
**Images** and **Video** (team to confirm before submitting).

- **Code:** yes. AI coding assistants (Anthropic Claude Code and OpenAI Codex) helped write and
  review code, tests and repository documentation. Team members reviewed every change through pull
  requests and CI.
- **Video:** yes. Veo (Google) made the background video clips, labeled "AI generated video".
- **Images:** yes. The logo and brand artwork were made with an AI image generator (name the tool),
  labeled "AI generated" in the app footer and on the project page. Claude made the video end card.
- **Text:** yes. Claude drafted the glossary and practice-card texts (reviewed by the team) and
  helped with the project backlog.
- **Data:** no. Crop data comes from FAO EcoCrop and climate, soil and moisture data come from NASA
  POWER, NASA SMAP, GPM IMERG, MERRA-2 and OpenLandMap. None of it is AI-generated, and no AI model
  produces the recommendations.

Paste for the project page ("Use of AI tools"):

> - **Veo (Google):** generated the background video clips used in the app and in our presentation
>   video. Each clip is labeled "AI generated".
> - **Claude (Anthropic):** created the end card of the video, drafted the glossary and the
>   regenerative-practice card texts, helped organize the project backlog, and helped write code for
>   the web app (Claude Code). All AI-drafted content was reviewed by the team.
> - **[Tool]:** generated the Terra Cosmos logo and brand artwork. Labeled "AI generated" wherever it
>   appears.
>
> NASA data and all scores come from our own code and public datasets (NASA POWER, SMAP, GPM IMERG,
> MERRA-2, OpenLandMap, FAO EcoCrop); no AI model produces the recommendations.

The form requires code and data to acknowledge SI in descriptive text and metadata. The README's
"Use of AI tools" section does this.

## 7. NASA Data (Link Text → Link URL)

| Link Text | Link URL |
|---|---|
| NASA POWER (Prediction Of Worldwide Energy Resources), daily and climatology API | https://power.larc.nasa.gov/ |
| NASA SMAP L4 Global 3-hourly 9 km Surface and Root Zone Soil Moisture, v8 (Reichle et al., NSIDC DAAC) | https://doi.org/10.5067/T5RUATAQREF8 |
| NASA SMAP L4 (SPL4SMGP/008) in Google Earth Engine | https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008 |
| NASA SRTM GL1 elevation (via OpenTopography). Only if we show terrain or erosion; it's not part of the ranking today | https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1 |

## 8. Space Agency Partner & Other Data (Link Text → Link URL)

| Link Text | Link URL |
|---|---|
| FAO EcoCrop crop requirements database | https://www.fao.org/geospatial/data-and-tools/data-portals/ecocrop/ |
| EcoCrop data via the CGIAR Africa Agriculture Adaptation Atlas | https://cgspace.cgiar.org/items/df16ec75-be74-4a57-aeec-6534a5893779 |
| OpenLandMap soil pH (Hengl, 2018; CC-BY-SA 4.0) | https://doi.org/10.5281/zenodo.1475457 |
| OpenLandMap soil layers in Google Earth Engine | https://developers.google.com/earth-engine/datasets/catalog/OpenLandMap_SOL_SOL_PH-H2O_USDA-4C1A2A_M_v02 |
| Google Earth Engine | https://earthengine.google.com/ |
| OpenTopography API | https://opentopography.org/ |
| FastAPI | https://fastapi.tiangolo.com/ |
| Railway (hosting) | https://railway.com/ |
| Cloudflare (DNS) | https://www.cloudflare.com/ |
| Anthropic Claude Code (AI coding assistant) | https://www.anthropic.com/claude-code |
| OpenAI Codex (AI coding assistant) | https://openai.com/codex/ |

Add anything else shown in the demo, for example Sentinel-2, ESA WorldCover or SoilGrids images
from `docs/pilot-baseline/`, with their links and licenses.
