"""Türkçe yerel ayar uyumlu FuzzyMatcher testleri."""

from __future__ import annotations

from qtp_app.ui.search import FuzzyMatcher, tr_lower


def test_turkish_locale_case_matching():
    matcher = FuzzyMatcher()

    # "şifre" -> "Şifrenizi"
    m_sifre = matcher.match_text("şifre", "Şifrenizi paylaşmayınız")
    assert m_sifre is not None
    assert m_sifre.matched_indices == (0, 1, 2, 3, 4)

    # "ı" ve "i" Türkçe ayrımı: "ılık" <-> "ILIK", "iade" <-> "İADE"
    assert tr_lower("ILIK") == "ılık"
    assert tr_lower("İADE") == "iade"
    assert matcher.match_text("ılık", "ILIK su") is not None
    assert matcher.match_text("iade", "İADE talebi") is not None
    assert matcher.match_text("ilgi", "ILGI") is None

    # Ğ/ğ, Ö/ö, Ü/ü, Ç/ç
    assert matcher.match_text("öğle", "ÖĞLE arası") is not None
    assert matcher.match_text("ücret", "ÜCRET iadesi") is not None
    assert matcher.match_text("çağrı", "ÇAĞRI merkezi") is not None
    assert matcher.match_text("değer", "DEĞERLENDİRME") is not None


def test_subsequence_scoring_stable_order():
    matcher = FuzzyMatcher()
    items = [
        {"keys": "L-Win+A", "group": "Restoran", "label": "Genel", "text": "Sipariş hazırlık süresi uzadı"},
        {"keys": "L-Win+Z", "group": "Kurye", "label": "Sipariş İptali", "text": "Sipariş iptal edildi"},
        {"keys": "L-Win+X", "group": "Müşteri", "label": "Bilgi", "text": "Sıradaki işlem için bekleyin"},
    ]

    run1 = matcher.filter_items("sip", items)
    run2 = matcher.filter_items("sip", items)
    run3 = matcher.filter_items("sip", items)

    order1 = [orig_idx for orig_idx, _it, _m in run1]
    assert order1 == [orig_idx for orig_idx, _it, _m in run2]
    assert order1 == [orig_idx for orig_idx, _it, _m in run3]
    assert set(order1) == {0, 1}
    # Etikette eşleşen "Sipariş İptali" yüksek puan almalı
    assert order1[0] == 1


def test_empty_query_returns_all_items_in_original_order():
    matcher = FuzzyMatcher()
    items = [
        {"keys": "L-Win+Q", "group": "G3", "text": "Üçüncü"},
        {"keys": "L-Win+A", "group": "G1", "text": "Birinci"},
        {"keys": "L-Win+Z", "group": "G2", "text": "İkinci"},
    ]

    res = matcher.filter_items("", items)
    assert [idx for idx, _it, _m in res] == [0, 1, 2]
    assert [it["text"] for _idx, it, _m in res] == ["Üçüncü", "Birinci", "İkinci"]
    assert all(indices == () for _idx, _it, indices in res)

    res_ws = matcher.filter_items("   ", items)
    assert [idx for idx, _it, _m in res_ws] == [0, 1, 2]


def test_fuzzy_subsequence_highlights_case_sensitive_and_edge_cases():
    assert tr_lower("") == ""
    matcher = FuzzyMatcher()

    # Kelimeler arası boşluklu alt-dizi eşleşmesi
    sub = matcher.match_text("spr ipt", "Sipariş iptal edildi")
    assert sub is not None
    assert len(sub.matched_indices) == 6

    # Boş hedef veya eşleşmeyen sorgu
    assert matcher.match_text("abc", "") is None
    assert matcher.match_text("xyz", "Merhaba") is None
    assert matcher.match_text("   ", "Merhaba").score == 0.0

    # Rozet (badge) ve grup araması
    item = {"keys": "L-Win+Q", "group": "Turkcell Hat", "label": "Kurulum", "text": "İşlem tamamlandı"}
    assert matcher.score_item("Q", item) is not None
    assert matcher.score_item("Turkcell", item) is not None
    assert matcher.score_item("   ", item).score == 0.0
    assert matcher.score_item("olmayan_terim", item) is None

    # Büyük/küçük harfe duyarlı mod
    cs = FuzzyMatcher(case_sensitive=True)
    assert cs.match_text("Merhaba", "Merhaba") is not None
    assert cs.match_text("merhaba", "Merhaba") is None

