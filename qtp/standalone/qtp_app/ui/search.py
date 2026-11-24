"""Türkçe yerel ayar uyumlu bulanık arama (FuzzyMatcher) motoru."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_TR_UPPER_TO_LOWER = str.maketrans({
    "İ": "i",
    "I": "ı",
    "Ş": "ş",
    "Ğ": "ğ",
    "Ü": "ü",
    "Ö": "ö",
    "Ç": "ç",
})

_TR_ALPHABET_ORDER = "abcçdefgğhıijklmnoöpqrsştuüvwxyz"
_TR_CHAR_RANK = {ch: (2, idx + 1) for idx, ch in enumerate(_TR_ALPHABET_ORDER)}


def tr_lower(text: str) -> str:
    """
    Türkçe büyük/küçük harf kurallarına göre küçültür.
    'İ' -> 'i', 'I' -> 'ı' dönüşümünü korur ve birleştirici nokta (U+0307) artıklarını temizler.
    """
    if not text:
        return ""
    return text.translate(_TR_UPPER_TO_LOWER).replace("\u0307", "").lower()


def tr_sort_key(text: str) -> tuple[tuple[int, int], ...]:
    """Türkçe alfabe sırası (a..z + ç,ğ,ı,ö,ş,ü) ve noktalama/rakam önceliği için sıralama anahtarı üretir."""
    norm = tr_lower(text or "")
    out: list[tuple[int, int]] = []
    for ch in norm:
        rank = _TR_CHAR_RANK.get(ch)
        if rank is not None:
            out.append(rank)
        elif ch.isdigit():
            out.append((1, int(ch)))
        elif ch.isspace() or not ch.isalnum():
            out.append((0, ord(ch)))
        else:
            out.append((3, ord(ch)))
    return tuple(out)


def _hotkey_badge(keys: str) -> str:
    raw = (keys or "").strip()
    if "+" in raw:
        return raw.rsplit("+", 1)[-1].strip().upper()
    return raw.upper()


@dataclass(frozen=True)
class FuzzyMatch:
    """Bulanık arama eşleşme sonucu."""

    score: float
    matched_indices: tuple[int, ...]


class FuzzyMatcher:
    """
    Bağımlılıksız, deterministik ve Türkçe yerel ayar uyumlu alt-dizi (subsequence) arayıcısı.
    """

    def __init__(self, *, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive

    def _norm(self, value: str) -> str:
        return value if self.case_sensitive else tr_lower(value)

    def match_text(self, query: str, target: str) -> FuzzyMatch | None:
        """
        Sorgunun hedef metin içindeki alt-dizi eşleşmesini puanlar ve indeksleri döndürür.
        Eşleşme yoksa None döndürür.
        """
        q_clean = self._norm(query.strip())
        if not q_clean:
            return FuzzyMatch(score=0.0, matched_indices=())

        t_norm = self._norm(target)
        if not t_norm:
            return None

        exact_pos = t_norm.find(q_clean)
        if exact_pos != -1:
            indices = tuple(range(exact_pos, exact_pos + len(q_clean)))
            boundary_bonus = 40.0 if (exact_pos == 0 or not t_norm[exact_pos - 1].isalnum()) else 15.0
            score = 200.0 + boundary_bonus - (exact_pos * 0.15) - (len(t_norm) * 0.01)
            return FuzzyMatch(score=score, matched_indices=indices)

        q_chars = [ch for ch in q_clean if not ch.isspace()]
        if not q_chars:
            return FuzzyMatch(score=0.0, matched_indices=())

        matched: list[int] = []
        t_idx = 0
        n = len(t_norm)
        for qch in q_chars:
            found = -1
            while t_idx < n:
                if t_norm[t_idx] == qch:
                    found = t_idx
                    t_idx += 1
                    break
                t_idx += 1
            if found == -1:
                return None
            matched.append(found)

        score = 80.0
        for pos_i, idx in enumerate(matched):
            if idx == 0 or not t_norm[idx - 1].isalnum():
                score += 12.0
            if pos_i > 0:
                gap = idx - matched[pos_i - 1] - 1
                if gap == 0:
                    score += 18.0
                else:
                    score -= min(gap * 1.2, 10.0)
        span = matched[-1] - matched[0] + 1
        score -= (span - len(matched)) * 0.4
        score -= matched[0] * 0.1
        return FuzzyMatch(score=score, matched_indices=tuple(matched))

    def score_item(self, query: str, item: dict[str, Any]) -> FuzzyMatch | None:
        """Öğeyi metin, etiket, grup ve kısayol alanlarında arar; vurgulanacak metin indekslerini döndürür."""
        q_clean = self._norm(query.strip())
        if not q_clean:
            return FuzzyMatch(score=0.0, matched_indices=())

        text_val = str(item.get("text", ""))
        label_val = str(item.get("label", ""))
        group_val = str(item.get("group", ""))
        badge_val = _hotkey_badge(str(item.get("keys", item.get("hotkey_prefix", ""))))

        text_match = self.match_text(query, text_val)
        label_match = self.match_text(query, label_val) if label_val else None
        group_match = self.match_text(query, group_val) if group_val else None
        badge_match = self.match_text(query, badge_val) if badge_val else None

        candidates: list[float] = []
        if text_match is not None:
            candidates.append(text_match.score + 10.0)
        if label_match is not None:
            candidates.append(label_match.score + 25.0)
        if group_match is not None:
            candidates.append(group_match.score + 5.0)
        if badge_match is not None:
            candidates.append(badge_match.score)

        if not candidates:
            return None

        best_score = max(candidates)
        indices = text_match.matched_indices if text_match is not None else ()
        return FuzzyMatch(score=best_score, matched_indices=indices)

    def filter_items(
        self,
        query: str,
        items: list[dict[str, Any]],
    ) -> list[tuple[int, dict[str, Any], tuple[int, ...]]]:
        """
        Öğeleri filtreler ve (orijinal_indeks, öğe, vurgulanan_indeksler) listesi döndürür.
        Boş sorguda tüm öğeler orijinal sırasıyla döndürülür.
        """
        q_stripped = (query or "").strip()
        if not q_stripped:
            return [(idx, item, ()) for idx, item in enumerate(items)]

        scored: list[tuple[float, int, dict[str, Any], tuple[int, ...]]] = []
        for idx, item in enumerate(items):
            res = self.match_item_or_none(q_stripped, item)
            if res is not None:
                scored.append((res.score, idx, item, res.matched_indices))

        scored.sort(key=lambda row: (-row[0], row[1]))
        return [(idx, item, indices) for _, idx, item, indices in scored]

    def match_item_or_none(self, query: str, item: dict[str, Any]) -> FuzzyMatch | None:
        return self.score_item(query, item)
