from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - depende do ambiente
    BeautifulSoup = None

try:
    from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depende do ambiente
    Browser = BrowserContext = Page = None
    PlaywrightTimeoutError = RuntimeError
    sync_playwright = None


@dataclass
class ElementSnapshot:
    value: str
    locator_description: str
    content_preview: str = ""


@dataclass
class CandidateField:
    label: str
    value: str
    context: str


class BrowserAutomation:
    IGNORED_LABEL_TERMS = {
        "reference",
        "copyright",
        "newsletter",
        "menu",
        "site",
        "investimentos",
        "economia",
        "uol",
    }
    SMART_SYNONYMS = {
        "dollar": "dolar",
        "usd": "dolar",
        "eur": "euro",
        "brl": "real",
        "btc": "bitcoin",
    }
    BLOCKED_PAGE_TERMS = (
        "reference #",
        "access denied",
        "request blocked",
        "captcha",
        "akamai",
        "attention required",
    )

    def __init__(self, timeout_seconds: float = 15.0, headless: bool = True) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def __enter__(self) -> "BrowserAutomation":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if sync_playwright is None:
            raise RuntimeError("Playwright nao esta instalado. Execute: pip install -r requirements.txt")

        if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            viewport={"width": 1440, "height": 900},
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout_seconds * 1000)

    def _open_page(self, url: str) -> None:
        page = self.page
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=min(int(self.timeout_seconds * 1000), 10000))
        except Exception:
            pass
        page.wait_for_timeout(1500)

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

        self._context = None
        self._browser = None
        self._playwright = None
        self._page = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("BrowserAutomation nao foi iniciado.")
        return self._page

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return normalized.lower().strip()

    def _clean_content_text(self, raw_text: str) -> str:
        lines = [re.sub(r"\s+", " ", line).strip() for line in (raw_text or "").splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)

    def _contains_numeric_signal(self, raw_text: str) -> bool:
        return bool(re.search(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?", raw_text or ""))

    def _extract_numeric_matches(self, raw_text: str) -> list[str]:
        return re.findall(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?", raw_text or "")

    def _looks_like_price(self, value: str) -> bool:
        candidate = (value or "").strip().replace("R$", "").replace(" ", "")
        if "," in candidate:
            return True
        if "." in candidate:
            return True
        return False

    def _extract_price_candidates(self, raw_text: str) -> list[str]:
        matches = self._extract_numeric_matches(raw_text)
        return [match.strip() for match in matches if self._looks_like_price(match)]

    def _looks_like_blocked_page(self, raw_text: str) -> bool:
        normalized = self._normalize_text(raw_text)
        return any(term in normalized for term in self.BLOCKED_PAGE_TERMS)

    def _extract_value_from_text(self, raw_text: str, keyword: str) -> str:
        text = self._clean_content_text(raw_text)
        normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
        keyword_candidates = self._build_smart_candidates(keyword)
        normalized_keywords = [self._normalize_text(candidate) for candidate in keyword_candidates]

        for index, line in enumerate(normalized_lines):
            normalized_line = self._normalize_text(line)
            if any(candidate in normalized_line for candidate in normalized_keywords):
                line_matches = self._extract_price_candidates(line)
                if line_matches:
                    return line_matches[0].strip()

                if index + 1 < len(normalized_lines):
                    next_line_matches = self._extract_price_candidates(normalized_lines[index + 1])
                    if next_line_matches:
                        return next_line_matches[0].strip()

        for priority_label in ("compra", "venda"):
            for line in normalized_lines:
                if priority_label in self._normalize_text(line):
                    line_matches = self._extract_price_candidates(line)
                    if line_matches:
                        return line_matches[0].strip()

        monetary_matches = self._extract_price_candidates(text)
        if monetary_matches:
            return monetary_matches[0].strip()

        for line in normalized_lines:
            if keyword.lower() not in line.lower():
                return line

        return text

    def _extract_context_lines(self, lines: list[str], start_index: int, max_lines: int = 4) -> str:
        return " | ".join(lines[start_index : start_index + max_lines])

    def _extract_label_from_line(self, line: str) -> str:
        cleaned = re.sub(r"\s+", " ", (line or "").strip(" -|:"))
        cleaned = re.sub(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|:")
        return cleaned

    def _is_meaningful_label(self, label: str) -> bool:
        normalized = self._normalize_text(label)
        if len(normalized) < 2:
            return False
        if normalized in self.IGNORED_LABEL_TERMS:
            return False
        if normalized.startswith("reference #"):
            return False
        return True

    def _build_smart_candidates(self, keyword: str) -> list[str]:
        raw_parts = re.split(r"[^A-Za-z0-9]+", keyword or "")
        candidates = []

        for part in [keyword, *raw_parts]:
            candidate = (part or "").strip()
            if len(candidate) >= 3 and candidate not in candidates:
                candidates.append(candidate)

        expanded_candidates = []
        for candidate in candidates:
            queue = [candidate]
            while queue:
                current = queue.pop(0)
                if current in expanded_candidates:
                    continue
                expanded_candidates.append(current)
                synonym = self.SMART_SYNONYMS.get(self._normalize_text(current))
                if synonym and synonym not in expanded_candidates:
                    queue.append(synonym)

        return expanded_candidates

    def _build_locator_description(self, mode: str, candidate: str, raw_text: str, box) -> str:
        cleaned_text = self._clean_content_text(raw_text)
        return f"{mode}={candidate} | content={cleaned_text[:160]!r} | bounding_box={box}"

    def _try_get_context_snapshot(self, locator, candidate: str, context_xpath: str, mode: str) -> Optional[ElementSnapshot]:
        context_locator = locator.locator(context_xpath).first
        try:
            raw_text = context_locator.inner_text().strip()
            if not self._contains_numeric_signal(raw_text):
                return None
            if self._looks_like_blocked_page(raw_text):
                return None

            box = context_locator.bounding_box()
            cleaned_text = self._clean_content_text(raw_text)
            return ElementSnapshot(
                value=self._extract_value_from_text(cleaned_text, candidate),
                locator_description=self._build_locator_description(mode, candidate, cleaned_text, box),
                content_preview=cleaned_text[:1000],
            )
        except Exception:
            return None

    def _try_get_finance_widget_snapshot(self, candidate: str) -> Optional[ElementSnapshot]:
        widget_selectors = [
            ".chart-info",
            "[class*='chart-info']",
            "[class*='cotacao']",
            "[class*='quote']",
            "[class*='currency']",
        ]

        for selector in widget_selectors:
            locator = self.page.locator(selector).first
            try:
                if locator.count() == 0:
                    continue

                raw_text = locator.inner_text().strip()
                if not self._contains_numeric_signal(raw_text):
                    continue
                if self._looks_like_blocked_page(raw_text):
                    continue

                box = locator.bounding_box()
                cleaned_text = self._clean_content_text(raw_text)
                return ElementSnapshot(
                    value=self._extract_value_from_text(cleaned_text, candidate),
                    locator_description=self._build_locator_description("smart-widget", candidate, cleaned_text, box),
                    content_preview=cleaned_text[:1000],
                )
            except Exception:
                continue

        return None

    def _find_text_match_in_page_content(self, keyword: str) -> Optional[ElementSnapshot]:
        if BeautifulSoup is None:
            return None

        content = self.page.content()
        soup = BeautifulSoup(content, "html.parser")
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        full_text = "\n".join(lines)
        if self._looks_like_blocked_page(full_text):
            raise ValueError("A pagina carregada parece ser uma tela de bloqueio ou erro do site, e nao a cotacao real.")

        normalized_keyword = self._normalize_text(keyword)

        for index, line in enumerate(lines):
            if normalized_keyword in self._normalize_text(line):
                context_text = self._extract_context_lines(lines, max(0, index - 1), 6)
                if not self._contains_numeric_signal(context_text):
                    continue
                if self._looks_like_blocked_page(context_text):
                    continue
                if not self._extract_price_candidates(context_text):
                    continue
                return ElementSnapshot(
                    value=self._extract_value_from_text(context_text, keyword),
                    locator_description=f"smart-content={keyword} | context={context_text[:160]!r}",
                    content_preview=self._clean_content_text(context_text)[:1000],
                )

        return None

    def discover_candidate_fields(self, url: str, limit: int = 12) -> list[CandidateField]:
        if BeautifulSoup is None:
            raise RuntimeError("BeautifulSoup nao esta instalado. Execute: pip install -r requirements.txt")

        self._open_page(url)
        content = self.page.content()
        soup = BeautifulSoup(content, "html.parser")
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        full_text = "\n".join(lines)

        if self._looks_like_blocked_page(full_text):
            raise ValueError("A pagina analisada parece ser uma tela de bloqueio ou erro do site. Tente recarregar ou usar outra URL.")

        candidates: list[CandidateField] = []
        seen: set[tuple[str, str]] = set()

        for index, line in enumerate(lines):
            if not self._contains_numeric_signal(line):
                continue

            label = self._extract_label_from_line(line)
            if len(label) < 2 and index > 0:
                label = self._extract_label_from_line(lines[index - 1])

            if not self._is_meaningful_label(label):
                continue

            value = self._extract_value_from_text(line, label)
            context = self._extract_context_lines(lines, max(0, index - 1), 3)
            key = (self._normalize_text(label), value)

            if key in seen:
                continue

            seen.add(key)
            candidates.append(CandidateField(label=label, value=value, context=context))

            if len(candidates) >= limit:
                break

        return candidates

    def _get_smart_value(self, keyword: str) -> ElementSnapshot:
        page = self.page
        candidates = self._build_smart_candidates(keyword)

        for candidate in candidates:
            locator = page.get_by_text(re.compile(re.escape(candidate), re.IGNORECASE)).first
            try:
                if locator.count() == 0:
                    continue
            except Exception:
                continue

            context_paths = [
                "xpath=ancestor::*[contains(@class,'chart-info')][1]",
                "xpath=ancestor::*[contains(@class,'card') or contains(@class,'row') or contains(@class,'table')][1]",
                "xpath=ancestor-or-self::*[self::tr or self::li or self::article or self::section or self::div][1]",
            ]

            for context_xpath in context_paths:
                snapshot = self._try_get_context_snapshot(locator, candidate, context_xpath, "smart")
                if snapshot:
                    return snapshot

            try:
                raw_text = locator.inner_text().strip()
                if not self._contains_numeric_signal(raw_text):
                    continue
                if self._looks_like_blocked_page(raw_text):
                    continue

                box = locator.bounding_box()
                cleaned_text = self._clean_content_text(raw_text)
                return ElementSnapshot(
                    value=self._extract_value_from_text(cleaned_text, candidate),
                    locator_description=self._build_locator_description("smart", candidate, cleaned_text, box),
                    content_preview=cleaned_text[:1000],
                )
            except Exception:
                continue

        for candidate in candidates:
            content_match = self._find_text_match_in_page_content(candidate)
            if content_match:
                return content_match

        for candidate in candidates:
            widget_match = self._try_get_finance_widget_snapshot(candidate)
            if widget_match:
                return widget_match

        raise ValueError(
            f"Nao foi possivel localizar automaticamente um valor numerico para: {keyword}. "
            "Informe o nome exato do ativo ou campo desejado, como Dolar, Euro, PETR4 ou VALE3."
        )

    def get_field_value(self, url: str, selector: str, selector_type: str) -> ElementSnapshot:
        self._open_page(url)
        page = self.page

        if selector_type == "smart":
            return self._get_smart_value(selector)

        if selector_type == "text":
            locator = page.get_by_text(selector, exact=False).first
            value = locator.inner_text().strip()
            box = locator.bounding_box()
            return ElementSnapshot(
                value=value,
                locator_description=f"text={selector} | bounding_box={box}",
                content_preview=value[:500],
            )

        if selector_type == "css":
            locator = page.locator(selector).first
            value = locator.inner_text().strip()
            box = locator.bounding_box()
            return ElementSnapshot(
                value=value,
                locator_description=f"css={selector} | bounding_box={box}",
                content_preview=value[:500],
            )

        if selector_type == "xpath":
            locator = page.locator(f"xpath={selector}").first
            value = locator.inner_text().strip()
            box = locator.bounding_box()
            return ElementSnapshot(
                value=value,
                locator_description=f"xpath={selector} | bounding_box={box}",
                content_preview=value[:500],
            )

        if selector_type == "regex":
            if BeautifulSoup is None:
                raise RuntimeError("BeautifulSoup nao esta instalado. Execute: pip install -r requirements.txt")
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            text = soup.get_text("\n", strip=True)
            match = re.search(selector, text)
            if not match:
                raise ValueError(f"Regex nao encontrou resultado: {selector}")
            return ElementSnapshot(
                value=match.group(0).strip(),
                locator_description=f"regex={selector} | page_text_length={len(text)}",
                content_preview=match.group(0).strip()[:500],
            )

        raise ValueError(f"Tipo de seletor nao suportado: {selector_type}")

    def post_update(self, url: str, input_selector: str, button_selector: str, message: str) -> None:
        self._open_page(url)
        page = self.page
        page.fill(input_selector, message)
        page.click(button_selector)

    def login_gmail_and_send(
        self,
        gmail_url: str,
        compose_selector: str,
        to_selector: str,
        subject_selector: str,
        body_selector: str,
        send_selector: str,
        recipient: str,
        subject: str,
        body: str,
    ) -> None:
        self._open_page(gmail_url)
        page = self.page
        try:
            page.click(compose_selector)
            page.fill(to_selector, recipient)
            page.fill(subject_selector, subject)
            page.fill(body_selector, body)
            page.click(send_selector)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "Falha ao interagir com o Gmail Web. Prefira SMTP com App Password para uso estavel."
            ) from exc
