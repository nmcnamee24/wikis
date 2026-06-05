#!/usr/bin/env python3
"""Generate Wikis topic-card JSON from Wikipedia.

This is Step 01 of the Wikis implementation plan. It proves the source pipeline:
Wikipedia API -> source snapshot -> related links -> image decision -> card JSON.

The default condenser is deterministic so the pipeline works without API keys.
Replace or extend `condense_with_heuristic` with an LLM provider once prompts are
ready to run in production.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import textwrap
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


API_URL = "https://en.wikipedia.org/w/api.php"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
USER_AGENT = "WikisStep01Prototype/0.1 (local development)"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
OPENAI_PROMPT_VERSION = "wikis-topic-page-v1"
VALID_PILLARS = {"science", "history", "society", "culture"}

PILLAR_KEYWORDS = {
    "science": [
        "physics",
        "biology",
        "astronomy",
        "mathematics",
        "technology",
        "science",
        "chemical",
        "planet",
        "star",
        "animal",
        "species",
        "computer",
        "theory",
    ],
    "culture": [
        "book",
        "novel",
        "poem",
        "poetry",
        "myth",
        "language",
        "story",
        "literature",
        "writer",
        "author",
        "epic",
        "art",
        "music",
        "film",
        "genre",
    ],
    "society": [
        "politics",
        "economics",
        "psychology",
        "culture",
        "society",
        "law",
        "religion",
        "government",
        "social",
        "movement",
        "institution",
    ],
    "history": [
        "history",
        "ancient",
        "war",
        "empire",
        "kingdom",
        "archaeology",
        "civilization",
        "century",
        "dynasty",
        "revolution",
    ],
}

WIKIS_CONTENT_SYSTEM_PROMPT = """You are the content-generation engine for Wikis, an app that lets users explore knowledge by moving deeper into a topic or branching into an adjacent idea.

You will receive a Wikipedia article for the current topic and a list of possible connected nodes.

Your task is to generate the exact content needed for one Wikis topic page.

Return:
The text displayed on the topic page.
The single pillar the topic belongs under.
One node that goes deeper into the current topic.
One node that branches to an adjacent topic.

Page Text:
Write 90-130 words explaining the topic.
The explanation should be understandable to a curious general reader, explain what the topic is and why it matters, include at least one important mechanism, cause, consequence, example, or surprising detail, provide more depth than a basic definition, avoid unnecessary names, dates, statistics, and technical terms, use short paragraphs suitable for a mobile screen, sound natural and engaging without sounding like social-media bait, use only facts supported by the supplied Wikipedia article, and select the most important ideas needed to understand the topic.

Pillar Classification:
Assign exactly one pillar: science, history, society, or culture.
Choose the pillar that best represents the topic's primary meaning.

Node Selection:
Select exactly two nodes from candidate_nodes.
The deeper node should explain a component, mechanism, subtopic, or more specific idea within the current topic.
The adjacent node should be closely related but not merely a component; it should move sideways into a new but meaningfully connected idea.
Do not classify a direct subcomponent as adjacent. Do not classify a broad parent category as deeper.

Quality checks before output:
The page text is between 90 and 130 words.
The explanation teaches more than a surface-level definition.
The deeper and adjacent nodes are different.
Every factual statement is supported by the supplied article or node context.
Return only valid JSON matching the schema."""

WIKIS_CONTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_text", "pillar", "deeper_node", "adjacent_node"],
    "properties": {
        "page_text": {"type": "string"},
        "pillar": {"type": "string", "enum": ["science", "history", "society", "culture"]},
        "deeper_node": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "connection"],
            "properties": {
                "name": {"type": "string"},
                "connection": {"type": "string"},
            },
        },
        "adjacent_node": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "connection"],
            "properties": {
                "name": {"type": "string"},
                "connection": {"type": "string"},
            },
        },
    },
}

BAD_IMAGE_PATTERNS = re.compile(
    r"(logo|flag|seal|coat[_ ]of[_ ]arms|icon|symbol|map|emblem|badge)",
    re.IGNORECASE,
)


class WikiLinkParser(HTMLParser):
    """Extract article links from the first meaningful paragraph."""

    def __init__(self) -> None:
        super().__init__()
        self.in_paragraph = False
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.paragraph_text: list[str] = []
        self.links: list[dict[str, str]] = []
        self.finished = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "p" and not self.finished and not self.in_paragraph:
            classes = attrs_dict.get("class", "")
            if "mw-empty-elt" not in classes:
                self.in_paragraph = True
        elif self.in_paragraph and tag in {"sup", "style", "script", "table"}:
            self.skip_depth += 1
        elif self.in_paragraph and self.skip_depth == 0 and tag == "a":
            self.current_href = attrs_dict.get("href")
            self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_paragraph and tag in {"sup", "style", "script", "table"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.in_paragraph and self.skip_depth == 0 and tag == "a" and self.current_href:
            text = clean_text("".join(self.current_text))
            title = title_from_wiki_href(self.current_href)
            if title and text:
                self.links.append({"title": title, "label": text})
            self.current_href = None
            self.current_text = []
        elif tag == "p" and self.in_paragraph:
            paragraph = clean_text("".join(self.paragraph_text))
            if paragraph:
                self.finished = True
            self.in_paragraph = False

    def handle_data(self, data: str) -> None:
        if not self.in_paragraph or self.skip_depth:
            return
        self.paragraph_text.append(data)
        if self.current_href is not None:
            self.current_text.append(data)


class AllWikiLinkParser(HTMLParser):
    """Extract all article links from a parsed HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[dict[str, str]] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"sup", "style", "script", "table"}:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag == "a":
            self.current_href = attrs_dict.get("href")
            self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"sup", "style", "script", "table"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth == 0 and tag == "a" and self.current_href:
            text = clean_text("".join(self.current_text))
            title = title_from_wiki_href(self.current_href)
            if title and text:
                self.links.append({"title": title, "label": text})
            self.current_href = None
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0 and self.current_href is not None:
            self.current_text.append(data)


@dataclass
class SourcePacket:
    requested_title: str
    normalized_title: str
    page_id: int
    revision_id: int | None
    extract: str
    lead_html: str
    first_paragraph: str
    first_paragraph_links: list[dict[str, str]]
    links: list[dict[str, str]]
    link_strategy: str
    image_candidates: list[dict[str, Any]]
    fetched_at: str


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\[[^\]]+\]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


def title_from_wiki_href(href: str) -> str | None:
    if not href.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(href.removeprefix("/wiki/").split("#", 1)[0])
    if not title:
        return None
    title = title.replace("_", " ")
    if ":" in title.rstrip(":"):
        return None
    return title


def wiki_api(params: dict[str, Any], *, retries: int = 5) -> dict[str, Any]:
    query = {"format": "json", "formatversion": 2, **params}
    url = f"{API_URL}?{urllib.parse.urlencode(query, doseq=True)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                time.sleep(min(45.0, 5.0 * (2**attempt)))
                continue
            time.sleep(0.4 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - surface network/API failures clearly.
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Wikipedia API request failed: {last_error}") from last_error


def parse_lead_html(page_title: str) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    data = wiki_api(
        {
            "action": "parse",
            "page": page_title,
            "prop": "text",
            "section": 0,
            "redirects": 1,
        }
    )
    lead_html = data["parse"]["text"]
    first_parser = WikiLinkParser()
    first_parser.feed(lead_html)
    lead_parser = AllWikiLinkParser()
    lead_parser.feed(lead_html)
    return lead_html, unique_links(first_parser.links), unique_links(lead_parser.links)


def unique_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for link in links:
        key = slugify(link["title"])
        if key not in seen:
            seen.add(key)
            out.append(link)
    return out


def fetch_source_packet(title: str) -> SourcePacket:
    page_data = wiki_api(
        {
            "action": "query",
            "titles": title,
            "redirects": 1,
            "prop": "extracts|info|pageimages",
            "exintro": 1,
            "explaintext": 1,
            "piprop": "thumbnail|original|name",
            "pithumbsize": 1600,
            "inprop": "url",
        }
    )
    pages = page_data["query"]["pages"]
    if not pages or pages[0].get("missing"):
        raise ValueError(f"Wikipedia page not found: {title}")

    page = pages[0]
    normalized_title = page["title"]
    extract = clean_text(page.get("extract", ""))
    lead_html, first_paragraph_links, lead_links = parse_lead_html(normalized_title)
    links = first_paragraph_links if len(first_paragraph_links) >= 3 else lead_links
    link_strategy = "first_paragraph" if len(first_paragraph_links) >= 3 else "lead_section_fallback"
    first_paragraph = first_sentence_group(extract, max_sentences=3)
    images = image_candidates_from_page(page)

    return SourcePacket(
        requested_title=title,
        normalized_title=normalized_title,
        page_id=int(page["pageid"]),
        revision_id=page.get("lastrevid"),
        extract=extract,
        lead_html=lead_html,
        first_paragraph=first_paragraph,
        first_paragraph_links=first_paragraph_links,
        links=links,
        link_strategy=link_strategy,
        image_candidates=images,
        fetched_at=dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
    )


def image_candidates_from_page(page: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pageimage = page.get("pageimage")
    thumbnail = page.get("thumbnail", {})
    original = page.get("original", {})
    source = original.get("source") or thumbnail.get("source")
    if source:
        width = original.get("width") or thumbnail.get("width")
        height = original.get("height") or thumbnail.get("height")
        rejection_reasons = score_image(pageimage or source, width, height)
        candidates.append(
            {
                "source": "wikipedia_pageimage",
                "title": pageimage,
                "url": source,
                "thumbnailUrl": thumbnail.get("source"),
                "width": width,
                "height": height,
                "qualityScore": 0.25 if rejection_reasons else 0.82,
                "rejectionReasons": rejection_reasons,
            }
        )
    return enrich_image_metadata(candidates)


def enrich_image_metadata(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    titles = [
        f"File:{candidate['title']}"
        for candidate in candidates
        if candidate.get("title")
    ]
    if not titles:
        return candidates

    try:
        metadata = wiki_api(
            {
                "action": "query",
                "titles": "|".join(titles),
                "prop": "imageinfo",
                "iiprop": "extmetadata|url|mime|size",
            }
        )
    except Exception:  # noqa: BLE001 - license enrichment should not block ingestion.
        return candidates

    by_title = {
        normalize_file_title(page.get("title", "").removeprefix("File:")): page
        for page in metadata.get("query", {}).get("pages", [])
    }
    for candidate in candidates:
        page = by_title.get(normalize_file_title(candidate.get("title", "")))
        imageinfo = (page or {}).get("imageinfo") or []
        extmetadata = imageinfo[0].get("extmetadata", {}) if imageinfo else {}
        candidate["license"] = metadata_value(extmetadata, "LicenseShortName") or metadata_value(extmetadata, "UsageTerms")
        candidate["attribution"] = clean_text(
            metadata_value(extmetadata, "Artist")
            or metadata_value(extmetadata, "Credit")
            or metadata_value(extmetadata, "ObjectName")
            or candidate.get("title")
            or ""
        )
        candidate["licenseUrl"] = metadata_value(extmetadata, "LicenseUrl")
        candidate["descriptionUrl"] = metadata_value(extmetadata, "DescriptionUrl")
        candidate["mime"] = imageinfo[0].get("mime") if imageinfo else None
    return candidates


def metadata_value(extmetadata: dict[str, Any], key: str) -> str | None:
    value = extmetadata.get(key, {}).get("value")
    if not value:
        return None
    return clean_text(re.sub(r"<[^>]+>", "", str(value)))


def normalize_file_title(value: str) -> str:
    return value.replace(" ", "_")


def score_image(name: str, width: int | None, height: int | None) -> list[str]:
    reasons: list[str] = []
    if BAD_IMAGE_PATTERNS.search(name or ""):
        reasons.append("weak_page_image_type")
    if width and height and min(width, height) < 700:
        reasons.append("low_resolution")
    return reasons


def select_image(packet: SourcePacket, pillar: str) -> dict[str, Any]:
    for candidate in packet.image_candidates:
        if not candidate["rejectionReasons"]:
            return {
                "strategy": "wikipedia_image",
                "selected": candidate,
                "candidates": packet.image_candidates,
                "fallbackPillar": None,
            }
    return {
        "strategy": "pillar_background",
        "selected": None,
        "candidates": packet.image_candidates,
        "fallbackPillar": pillar,
        "reason": "no_suitable_wikipedia_image",
    }


def classify_pillar(title: str, extract: str, links: list[dict[str, str]]) -> str:
    text = " ".join([title, extract[:1200], " ".join(link["title"] for link in links)]).lower()
    scores = {
        pillar: sum(1 for keyword in keywords if keyword in text)
        for pillar, keywords in PILLAR_KEYWORDS.items()
    }
    return max(scores, key=lambda pillar: (scores[pillar], pillar))


def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def first_sentence_group(text: str, max_sentences: int = 4) -> str:
    sentences = split_sentences(text)
    return " ".join(sentences[:max_sentences])


def trim_to_word_count(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed = " ".join(words[:max_words]).rstrip(",;:")
    return f"{trimmed}."


def estimate_reading_seconds(text: str) -> int:
    words = len(text.split())
    return max(8, round(words / 3.8))


def condense_with_heuristic(packet: SourcePacket, pillar: str) -> dict[str, Any]:
    title = packet.normalized_title
    sentences = split_sentences(packet.extract)
    opening = sentences[0] if sentences else f"{title} is a topic documented by Wikipedia."
    followup = " ".join(sentences[1:4])
    explanation = clean_text(f"{opening} {followup}")
    explanation = trim_to_word_count(explanation, 105)

    links = [link["title"] for link in packet.links[:8]]
    if links:
        hook = f"It connects quickly to {links[0]}, which is why one topic can open into a much larger rabbit hole."
    else:
        hook = "Its deeper story comes from how many different fields use it to explain something bigger."

    return {
        "title": title,
        "pillar": pillar,
        "explanation": explanation,
        "hookType": "the_weird_part",
        "hook": hook,
        "relatedCandidates": links,
        "readingSeconds": estimate_reading_seconds(f"{explanation} {hook}"),
        "confidenceNotes": ["Generated by deterministic local condenser from Wikipedia extract."],
    }


def condense_with_openai(packet: SourcePacket, model: str | None = None) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --condenser openai")

    candidate_nodes = [
        {"name": link["title"], "context": link.get("label", "")}
        for link in packet.links[:16]
    ]
    if len(candidate_nodes) < 2:
        raise RuntimeError("OpenAI condenser requires at least two candidate nodes")

    request_payload = {
        "model": model or os.environ.get("WIKIS_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": WIKIS_CONTENT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "topic": packet.normalized_title,
                        "wikipedia_article": packet.extract,
                        "candidate_nodes": candidate_nodes,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "wikis_topic_page",
                "strict": True,
                "schema": WIKIS_CONTENT_SCHEMA,
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Responses API failed: HTTP {exc.code}: {body}") from exc

    content = extract_response_text(response_payload)
    generated = json.loads(content)
    validation_issues = validate_llm_topic_page(generated, candidate_nodes)
    if validation_issues:
        raise RuntimeError(f"OpenAI condenser returned invalid topic page: {', '.join(validation_issues)}")

    deeper = generated["deeper_node"]
    adjacent = generated["adjacent_node"]
    return {
        "title": packet.normalized_title,
        "pillar": generated["pillar"],
        "explanation": generated["page_text"],
        "hookType": "why_it_matters",
        "hook": adjacent["connection"],
        "relatedCandidates": [deeper["name"], adjacent["name"]],
        "navigationNodes": {
            "deeper": deeper,
            "adjacent": adjacent,
        },
        "readingSeconds": estimate_reading_seconds(generated["page_text"]),
        "confidenceNotes": [
            f"Generated with OpenAI Responses API model {request_payload['model']}.",
            f"Prompt version: {OPENAI_PROMPT_VERSION}.",
        ],
        "generationProvider": "openai",
        "generationModel": request_payload["model"],
        "promptVersion": OPENAI_PROMPT_VERSION,
    }


def extract_response_text(response_payload: dict[str, Any]) -> str:
    if response_payload.get("output_text"):
        return str(response_payload["output_text"])
    chunks: list[str] = []
    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output text")
    return "".join(chunks)


def validate_llm_topic_page(page: dict[str, Any], candidate_nodes: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []
    page_text = page.get("page_text", "")
    word_count = len(page_text.split())
    if word_count < 90:
        issues.append("page_text_too_short")
    if word_count > 130:
        issues.append("page_text_too_long")
    if page.get("pillar") not in VALID_PILLARS:
        issues.append("invalid_pillar")
    candidate_names = {candidate["name"] for candidate in candidate_nodes}
    deeper_name = page.get("deeper_node", {}).get("name")
    adjacent_name = page.get("adjacent_node", {}).get("name")
    if deeper_name not in candidate_names:
        issues.append("deeper_node_not_in_candidates")
    if adjacent_name not in candidate_names:
        issues.append("adjacent_node_not_in_candidates")
    if deeper_name == adjacent_name:
        issues.append("duplicate_navigation_nodes")
    return issues


def validate_card(card: dict[str, Any], packet: SourcePacket, image_decision: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not card["explanation"] or len(card["explanation"].split()) < 35:
        issues.append("explanation_too_short")
    if len(card["explanation"].split()) > 140:
        issues.append("explanation_too_long")
    if card["pillar"] not in VALID_PILLARS:
        issues.append("invalid_pillar")
    if card["hookType"] not in {
        "the_weird_part",
        "why_it_matters",
        "scientists_still_dont_know",
        "the_twist",
        "the_surprising_part",
    }:
        issues.append("invalid_hook_type")
    if not card["hook"]:
        issues.append("missing_hook")
    if len(packet.links) < 3:
        issues.append("few_related_candidates")
    if image_decision["strategy"] == "wikipedia_image":
        selected = image_decision["selected"]
        if selected and selected.get("rejectionReasons"):
            issues.append("selected_image_has_rejection_reasons")
    if card.get("generationProvider") == "openai":
        word_count = len(card["explanation"].split())
        if word_count < 90:
            issues.append("llm_page_text_too_short")
        if word_count > 130:
            issues.append("llm_page_text_too_long")
        navigation_nodes = card.get("navigationNodes", {})
        if not navigation_nodes.get("deeper") or not navigation_nodes.get("adjacent"):
            issues.append("missing_navigation_nodes")
    return issues


def build_card_output(title: str, condenser: str = "local", model: str | None = None) -> dict[str, Any]:
    packet = fetch_source_packet(title)
    pillar = classify_pillar(packet.normalized_title, packet.extract, packet.links)
    if condenser == "openai":
        card = condense_with_openai(packet, model)
        pillar = card["pillar"]
    else:
        card = condense_with_heuristic(packet, pillar)
    image_decision = select_image(packet, pillar)
    validation_issues = validate_card(card, packet, image_decision)

    return {
        "schemaVersion": 1,
        "generatedAt": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "generation": {
            "provider": card.get("generationProvider", "local"),
            "model": card.get("generationModel", "deterministic-wikipedia-condenser"),
            "promptVersion": card.get("promptVersion", "step-01-local-v1"),
        },
        "source": {
            "requestedTitle": packet.requested_title,
            "wikipediaTitle": packet.normalized_title,
            "pageId": packet.page_id,
            "revisionId": packet.revision_id,
            "fetchedAt": packet.fetched_at,
            "extract": packet.extract,
            "firstParagraph": packet.first_paragraph,
            "leadHtml": packet.lead_html,
        },
        "card": card,
        "mapping": {
            "linkStrategy": packet.link_strategy,
            "firstParagraphLinks": packet.first_paragraph_links,
            "leadOrFallbackLinks": packet.links,
            "relatedTopicCandidates": card["relatedCandidates"],
        },
        "image": image_decision,
        "quality": {
            "status": "needs_review" if validation_issues else "prototype_pass",
            "issues": validation_issues,
        },
    }


def write_card(output_dir: Path, card_output: dict[str, Any]) -> Path:
    title = card_output["source"]["wikipediaTitle"]
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{slugify(title)}.json"
    path.write_text(json.dumps(card_output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Wikis card JSON from Wikipedia titles.")
    parser.add_argument("titles", nargs="*", help="Wikipedia page titles to ingest.")
    parser.add_argument(
        "--titles-file",
        type=Path,
        help="Plain text file containing one Wikipedia page title per line.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/cards"),
        help="Output directory for generated card JSON.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between titles to avoid hammering the Wikipedia API.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip titles whose output JSON already exists.",
    )
    parser.add_argument(
        "--condenser",
        choices=["local", "openai"],
        default="local",
        help="Use the deterministic local condenser or the OpenAI structured-output condenser.",
    )
    parser.add_argument(
        "--openai-model",
        default=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        help="OpenAI model to use when --condenser openai.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    titles = list(args.titles)
    if args.titles_file:
        file_titles = [
            line.strip()
            for line in args.titles_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        titles.extend(file_titles)
    if not titles:
        print("ERROR: provide at least one title or --titles-file", file=sys.stderr)
        return 2

    failures = 0
    for index, title in enumerate(titles):
        output_path = args.out / f"{slugify(title)}.json"
        if args.skip_existing and output_path.exists():
            print(f"{title} -> {output_path} (skipped)")
            continue
        try:
            card_output = build_card_output(title, condenser=args.condenser, model=args.openai_model)
            path = write_card(args.out, card_output)
            status = card_output["quality"]["status"]
            print(f"{title} -> {path} ({status})")
        except Exception as exc:  # noqa: BLE001 - CLI should continue through title list.
            failures += 1
            print(f"ERROR: {title}: {exc}", file=sys.stderr)
        if index < len(titles) - 1 and args.delay > 0:
            time.sleep(args.delay)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
