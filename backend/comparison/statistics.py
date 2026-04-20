"""
Статистические функции для двухрежимного сравнительного анализа прогонов.

Содержит:
- Описательная статистика и box plot
- Попарное сравнение выборок (Welch / Mann–Whitney), Cohen's d, CI
- FDR-коррекция (Benjamini-Hochberg)
- Тренд-тесты для серийного режима (Spearman, Mann–Kendall)
- Индексы серии: деградация, устойчивость, эластичность, точка насыщения
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from scipy import stats as sp_stats
except ImportError:  # pragma: no cover
    sp_stats = None

from backend.comparison.schemas import (
    DegradationIndex,
    DescriptiveStats,
    PairwiseComparison,
    TrendTestResult,
)


MIN_SAMPLE_SIZE_FOR_TEST = 10
NORMALITY_SAMPLE_LIMIT = 5000
SIGNIFICANCE_LEVEL = 0.05

EFFECT_SIZE_THRESHOLDS = [
    (0.2, "negligible"),
    (0.5, "small"),
    (0.8, "medium"),
    (float("inf"), "large"),
]


def _ensure_dependencies_available():
    """Проверить, что аналитические зависимости доступны"""
    if np is None or sp_stats is None:
        raise RuntimeError(
            "Для сравнительного анализа требуются numpy и scipy. "
            "Установите зависимости из requirements.txt"
        )


def _sanitize_numeric_data(data: List[float]) -> List[float]:
    """Очистить выборку от нечисловых и некорректных значений"""
    clean_data = []
    for value in data:
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(numeric_value) or math.isinf(numeric_value):
            continue
        clean_data.append(numeric_value)
    return clean_data


# ---------------------------------------------------------------------------
# Описательная статистика
# ---------------------------------------------------------------------------

def calculate_descriptive_stats(data: List[float]) -> DescriptiveStats:
    """Рассчитать описательную статистику по выборке"""
    _ensure_dependencies_available()

    clean_data = _sanitize_numeric_data(data)
    if not clean_data:
        raise ValueError("Невозможно рассчитать статистику: выборка пуста")

    std_value = 0.0 if len(clean_data) == 1 else float(np.std(clean_data, ddof=1))
    mean_value = float(np.mean(clean_data))
    q1 = float(np.percentile(clean_data, 25))
    q3 = float(np.percentile(clean_data, 75))

    return DescriptiveStats(
        count=len(clean_data),
        mean=mean_value,
        median=float(np.median(clean_data)),
        std=std_value,
        min=float(np.min(clean_data)),
        max=float(np.max(clean_data)),
        p50=float(np.percentile(clean_data, 50)),
        p95=float(np.percentile(clean_data, 95)),
        p99=float(np.percentile(clean_data, 99)),
        cv=std_value / mean_value if mean_value != 0 else 0.0,
        iqr=q3 - q1,
    )


def calculate_box_plot_stats(data: List[float]) -> Dict[str, float]:
    """Рассчитать five-number summary для box plot"""
    _ensure_dependencies_available()

    clean_data = _sanitize_numeric_data(data)
    if not clean_data:
        raise ValueError("Невозможно рассчитать box plot: выборка пуста")

    return {
        "min": float(np.min(clean_data)),
        "q1": float(np.percentile(clean_data, 25)),
        "median": float(np.percentile(clean_data, 50)),
        "q3": float(np.percentile(clean_data, 75)),
        "max": float(np.max(clean_data)),
        "sample_count": len(clean_data),
    }


# ---------------------------------------------------------------------------
# Проверка нормальности
# ---------------------------------------------------------------------------

def check_normality(data: List[float]) -> bool:
    """Проверить нормальность распределения по Shapiro-Wilk"""
    _ensure_dependencies_available()

    clean_data = _sanitize_numeric_data(data)
    if len(clean_data) < MIN_SAMPLE_SIZE_FOR_TEST:
        return False

    sample = clean_data[:NORMALITY_SAMPLE_LIMIT]
    try:
        _, p_value = sp_stats.shapiro(sample)
    except Exception:
        return False
    return bool(p_value > SIGNIFICANCE_LEVEL)


# ---------------------------------------------------------------------------
# Размер эффекта и доверительный интервал
# ---------------------------------------------------------------------------

def calculate_cohens_d(a: List[float], b: List[float]) -> Optional[float]:
    """Рассчитать Cohen's d — стандартизированный размер эффекта"""
    if len(a) < 2 or len(b) < 2:
        return None

    mean_a, mean_b = float(np.mean(a)), float(np.mean(b))
    std_a, std_b = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    na, nb = len(a), len(b)

    pooled_std = math.sqrt(((na - 1) * std_a ** 2 + (nb - 1) * std_b ** 2) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    return (mean_b - mean_a) / pooled_std


def classify_effect_size(d: Optional[float]) -> Optional[str]:
    """Классифицировать Cohen's d по стандартным порогам"""
    if d is None:
        return None
    abs_d = abs(d)
    for threshold, label in EFFECT_SIZE_THRESHOLDS:
        if abs_d < threshold:
            return label
    return "large"


def calculate_confidence_interval(
    a: List[float], b: List[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Рассчитать 95% CI для разницы средних (Welch)"""
    if len(a) < 2 or len(b) < 2:
        return None, None

    mean_diff = float(np.mean(b)) - float(np.mean(a))
    var_a = float(np.var(a, ddof=1)) / len(a)
    var_b = float(np.var(b, ddof=1)) / len(b)
    se = math.sqrt(var_a + var_b)

    numerator = (var_a + var_b) ** 2
    denominator = var_a ** 2 / (len(a) - 1) + var_b ** 2 / (len(b) - 1)
    if denominator == 0:
        return None, None
    df = numerator / denominator

    try:
        t_crit = float(sp_stats.t.ppf(1 - SIGNIFICANCE_LEVEL / 2, df))
    except Exception:
        return None, None

    margin = t_crit * se
    return mean_diff - margin, mean_diff + margin


# ---------------------------------------------------------------------------
# Интерпретация
# ---------------------------------------------------------------------------

def safe_pct_difference(baseline: float, compared: float) -> Optional[float]:
    """Безопасно рассчитать процентное отличие от baseline"""
    if baseline == 0:
        return None
    return ((compared - baseline) / baseline) * 100.0


def interpret_result(
    pct_diff: Optional[float],
    p_value: Optional[float],
    metric: str,
    effect_label: Optional[str] = None,
) -> str:
    """Сформировать текстовую интерпретацию результата"""
    if p_value is None:
        return "Недостаточно данных для статистического теста"
    if p_value >= SIGNIFICANCE_LEVEL:
        return "Разница статистически незначима"
    if pct_diff is None:
        return "Невозможно рассчитать процентное отличие относительно baseline"

    effect_note = ""
    if effect_label and effect_label != "negligible":
        effect_ru = {"small": "малый", "medium": "средний", "large": "большой"}.get(
            effect_label, effect_label
        )
        effect_note = f", {effect_ru} эффект"

    if metric == "latency_ms":
        if pct_diff > 0:
            return f"Сравниваемая СУБД медленнее на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"
        return f"Сравниваемая СУБД быстрее на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"

    if pct_diff > 0:
        return f"Сравниваемая СУБД показывает прирост на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"
    return f"Сравниваемая СУБД показывает снижение на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"


# ---------------------------------------------------------------------------
# Попарное сравнение двух выборок
# ---------------------------------------------------------------------------

def compare_two_samples(
    a: List[float],
    b: List[float],
    baseline_id: str,
    compared_id: str,
    db_key: str,
    metric: str,
) -> PairwiseComparison:
    """Сравнить две выборки и рассчитать статистическую значимость"""
    _ensure_dependencies_available()

    sample_a = _sanitize_numeric_data(a)
    sample_b = _sanitize_numeric_data(b)

    comparison = PairwiseComparison(
        baseline_id=str(baseline_id),
        compared_id=str(compared_id),
        db_key=db_key,
        metric=metric,
        interpretation="Недостаточно данных для статистического теста",
        warning=None,
    )

    if not sample_a or not sample_b:
        comparison.warning = "Одна из выборок пуста"
        return comparison

    mean_a = float(np.mean(sample_a))
    mean_b = float(np.mean(sample_b))
    pct_diff = safe_pct_difference(mean_a, mean_b)

    comparison.baseline_mean = mean_a
    comparison.compared_mean = mean_b
    comparison.pct_difference = pct_diff

    d = calculate_cohens_d(sample_a, sample_b)
    comparison.effect_size = d
    comparison.effect_size_label = classify_effect_size(d)

    ci_lo, ci_hi = calculate_confidence_interval(sample_a, sample_b)
    comparison.ci_lower = ci_lo
    comparison.ci_upper = ci_hi

    if len(sample_a) < MIN_SAMPLE_SIZE_FOR_TEST or len(sample_b) < MIN_SAMPLE_SIZE_FOR_TEST:
        comparison.warning = (
            f"Недостаточно данных для статистического теста: "
            f"n_baseline={len(sample_a)}, n_compared={len(sample_b)}"
        )
        comparison.interpretation = interpret_result(
            pct_diff, None, metric, comparison.effect_size_label,
        )
        return comparison

    is_normal = check_normality(sample_a) and check_normality(sample_b)

    try:
        if is_normal:
            statistic, p_value = sp_stats.ttest_ind(sample_a, sample_b, equal_var=False)
            test_used = "welch_ttest"
        else:
            statistic, p_value = sp_stats.mannwhitneyu(
                sample_a, sample_b, alternative="two-sided",
            )
            test_used = "mann_whitney_u"
    except Exception as exc:
        comparison.warning = f"Ошибка статистического теста: {exc}"
        comparison.interpretation = interpret_result(
            pct_diff, None, metric, comparison.effect_size_label,
        )
        return comparison

    comparison.test_used = test_used
    comparison.statistic = float(statistic)
    comparison.p_value = float(p_value)
    comparison.is_significant = bool(p_value < SIGNIFICANCE_LEVEL)
    comparison.interpretation = interpret_result(
        pct_diff, float(p_value), metric, comparison.effect_size_label,
    )
    return comparison


# ---------------------------------------------------------------------------
# FDR-коррекция (Benjamini-Hochberg)
# ---------------------------------------------------------------------------

def apply_fdr_correction(comparisons: Sequence[PairwiseComparison]) -> None:
    """Применить FDR-коррекцию in-place к списку попарных сравнений."""
    indexed: list[tuple[int, float]] = []
    for i, c in enumerate(comparisons):
        if c.p_value is not None:
            indexed.append((i, c.p_value))

    if not indexed:
        return

    indexed.sort(key=lambda t: t[1])
    m = len(indexed)

    adjusted = [0.0] * m
    for rank_0, (_, p) in enumerate(indexed):
        rank = rank_0 + 1
        adjusted[rank_0] = p * m / rank

    for k in range(m - 2, -1, -1):
        adjusted[k] = min(adjusted[k], adjusted[k + 1])

    for rank_0, (orig_idx, _) in enumerate(indexed):
        adj_p = min(adjusted[rank_0], 1.0)
        comparisons[orig_idx].p_value_adjusted = adj_p
        comparisons[orig_idx].is_significant_adjusted = adj_p < SIGNIFICANCE_LEVEL


# ---------------------------------------------------------------------------
# Тренд-тесты для серийного режима
# ---------------------------------------------------------------------------

def spearman_correlation(
    x: List[float], y: List[float],
) -> Optional[TrendTestResult]:
    """Рассчитать корреляцию Спирмена между уровнями нагрузки и метрикой."""
    _ensure_dependencies_available()

    clean_x = _sanitize_numeric_data(x)
    clean_y = _sanitize_numeric_data(y)
    if len(clean_x) < 3 or len(clean_x) != len(clean_y):
        return None

    try:
        stat, p_val = sp_stats.spearmanr(clean_x, clean_y)
    except Exception:
        return None

    if p_val < SIGNIFICANCE_LEVEL:
        direction = "increasing" if stat > 0 else "decreasing"
    else:
        direction = "no_trend"

    return TrendTestResult(statistic=float(stat), p_value=float(p_val), direction=direction)


def mann_kendall_trend(values: List[float]) -> Optional[TrendTestResult]:
    """Тест Манна–Кендалла на монотонный тренд.

    Реализация без внешних библиотек: S-статистика, нормальное приближение
    при n >= 8, точная при n < 8 (используем Spearman как fallback).
    """
    _ensure_dependencies_available()

    clean = _sanitize_numeric_data(values)
    n = len(clean)
    if n < 3:
        return None

    if n < 8:
        return spearman_correlation(list(range(n)), clean)

    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = clean[j] - clean[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1

    var_s = n * (n - 1) * (2 * n + 5) / 18.0

    if var_s == 0:
        return TrendTestResult(statistic=0.0, p_value=1.0, direction="no_trend")

    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0

    p_val = 2.0 * (1.0 - float(sp_stats.norm.cdf(abs(z))))

    if p_val < SIGNIFICANCE_LEVEL:
        direction = "increasing" if s > 0 else "decreasing"
    else:
        direction = "no_trend"

    return TrendTestResult(statistic=float(z), p_value=float(p_val), direction=direction)


# ---------------------------------------------------------------------------
# Индексы серии
# ---------------------------------------------------------------------------

def calculate_degradation_index(
    p95_values: List[float], p99_values: List[float],
) -> DegradationIndex:
    """Рассчитать индекс деградации перцентилей по уровням нагрузки.

    Для каждого перехода между соседними уровнями считается процентное
    изменение p95 и p99. overall — среднее всех изменений.
    """
    p95_clean = _sanitize_numeric_data(p95_values)
    p99_clean = _sanitize_numeric_data(p99_values)

    p95_changes = []
    for i in range(1, len(p95_clean)):
        if p95_clean[i - 1] != 0:
            pct = ((p95_clean[i] - p95_clean[i - 1]) / p95_clean[i - 1]) * 100.0
            p95_changes.append(round(pct, 2))

    p99_changes = []
    for i in range(1, len(p99_clean)):
        if p99_clean[i - 1] != 0:
            pct = ((p99_clean[i] - p99_clean[i - 1]) / p99_clean[i - 1]) * 100.0
            p99_changes.append(round(pct, 2))

    overall_p95 = round(float(np.mean(p95_changes)), 2) if p95_changes else 0.0
    overall_p99 = round(float(np.mean(p99_changes)), 2) if p99_changes else 0.0

    return DegradationIndex(
        p95_changes=p95_changes,
        p99_changes=p99_changes,
        overall_p95=overall_p95,
        overall_p99=overall_p99,
    )


def calculate_stability_index(cv_values: List[float]) -> Optional[float]:
    """Рассчитать индекс устойчивости: среднее CV + дисперсия CV.

    Чем меньше значение, тем стабильнее СУБД по всем уровням нагрузки.
    """
    clean = _sanitize_numeric_data(cv_values)
    if len(clean) < 2:
        return None
    mean_cv = float(np.mean(clean))
    var_cv = float(np.var(clean, ddof=1))
    return round(mean_cv + var_cv, 4)


def calculate_elasticity(
    throughput_values: List[float], thread_counts: List[int],
) -> Optional[float]:
    """Рассчитать эластичность пропускной способности.

    Нормализованная средняя производная d(throughput)/d(threads),
    выраженная как процентное изменение throughput на процент изменения threads.
    Значение 1.0 = идеальное линейное масштабирование.
    """
    clean_tp = _sanitize_numeric_data(throughput_values)
    clean_threads = _sanitize_numeric_data([float(t) for t in thread_counts])

    if len(clean_tp) < 2 or len(clean_tp) != len(clean_threads):
        return None

    elasticities = []
    for i in range(1, len(clean_tp)):
        if clean_tp[i - 1] == 0 or clean_threads[i - 1] == 0:
            continue
        pct_tp = (clean_tp[i] - clean_tp[i - 1]) / clean_tp[i - 1]
        pct_threads = (clean_threads[i] - clean_threads[i - 1]) / clean_threads[i - 1]
        if pct_threads != 0:
            elasticities.append(pct_tp / pct_threads)

    if not elasticities:
        return None
    return round(float(np.mean(elasticities)), 4)


def detect_saturation_point(
    throughput_values: List[float],
    p95_values: List[float],
    level_ids: List[str],
    threshold_tp_growth: float = 0.05,
    threshold_p95_accel: float = 0.5,
) -> Optional[str]:
    """Определить точку насыщения: первый уровень, после которого throughput
    перестаёт расти (< threshold_tp_growth) или p95 ускоряется выше порога.

    Возвращает level_id точки насыщения или None.
    """
    clean_tp = _sanitize_numeric_data(throughput_values)
    clean_p95 = _sanitize_numeric_data(p95_values)
    n = min(len(clean_tp), len(clean_p95), len(level_ids))
    if n < 2:
        return None

    prev_p95_change = None
    for i in range(1, n):
        if clean_tp[i - 1] == 0:
            continue

        tp_growth = (clean_tp[i] - clean_tp[i - 1]) / clean_tp[i - 1]

        if tp_growth < threshold_tp_growth:
            return level_ids[i]

        if clean_p95[i - 1] != 0:
            p95_change = (clean_p95[i] - clean_p95[i - 1]) / clean_p95[i - 1]
            if prev_p95_change is not None and p95_change > 0:
                acceleration = p95_change - prev_p95_change if prev_p95_change >= 0 else p95_change
                if acceleration > threshold_p95_accel:
                    return level_ids[i]
            prev_p95_change = p95_change

    return None
