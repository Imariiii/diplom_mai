"""
Статистические функции для сравнительного анализа тестов
"""
import math
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover - зависит от окружения
    np = None

try:
    from scipy import stats as sp_stats
except ImportError:  # pragma: no cover - зависит от окружения
    sp_stats = None

from backend.comparison.schemas import DescriptiveStats, PairwiseComparison


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
            "Для сравнительного анализа требуются numpy и scipy. Установите зависимости из requirements.txt"
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


def calculate_descriptive_stats(data: List[float]) -> DescriptiveStats:
    """Рассчитать описательную статистику по выборке"""
    _ensure_dependencies_available()

    clean_data = _sanitize_numeric_data(data)
    if not clean_data:
        raise ValueError("Невозможно рассчитать статистику: выборка пуста")

    if len(clean_data) == 1:
        std_value = 0.0
    else:
        std_value = float(np.std(clean_data, ddof=1))

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


def calculate_cohens_d(a: List[float], b: List[float]) -> Optional[float]:
    """Рассчитать Cohen's d — стандартизированный размер эффекта"""
    if len(a) < 2 or len(b) < 2:
        return None

    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    std_a = float(np.std(a, ddof=1))
    std_b = float(np.std(b, ddof=1))
    na = len(a)
    nb = len(b)

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
    a: List[float], b: List[float]
) -> Tuple[Optional[float], Optional[float]]:
    """Рассчитать 95% CI для разницы средних (Welch)"""
    if len(a) < 2 or len(b) < 2:
        return None, None

    mean_diff = float(np.mean(b)) - float(np.mean(a))
    se = math.sqrt(
        float(np.var(a, ddof=1)) / len(a) + float(np.var(b, ddof=1)) / len(b)
    )

    var_a = float(np.var(a, ddof=1)) / len(a)
    var_b = float(np.var(b, ddof=1)) / len(b)
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
        effect_ru = {
            "small": "малый",
            "medium": "средний",
            "large": "большой",
        }.get(effect_label, effect_label)
        effect_note = f", {effect_ru} эффект"

    if metric == "latency_ms":
        if pct_diff > 0:
            return f"Сравниваемый тест медленнее на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"
        return f"Сравниваемый тест быстрее на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"

    if pct_diff > 0:
        return f"Сравниваемый тест показывает прирост на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"
    return f"Сравниваемый тест показывает снижение на {abs(pct_diff):.1f}% (p={p_value:.4f}{effect_note})"


def compare_two_samples(
    a: List[float],
    b: List[float],
    baseline_test_id,
    compared_test_id,
    db_key: str,
    metric: str,
) -> PairwiseComparison:
    """Сравнить две выборки и рассчитать статистическую значимость"""
    _ensure_dependencies_available()

    sample_a = _sanitize_numeric_data(a)
    sample_b = _sanitize_numeric_data(b)

    comparison = PairwiseComparison(
        baseline_test_id=baseline_test_id,
        compared_test_id=compared_test_id,
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
            f"Недостаточно данных для статистического теста: n_baseline={len(sample_a)}, n_compared={len(sample_b)}"
        )
        comparison.interpretation = interpret_result(pct_diff, None, metric, comparison.effect_size_label)
        return comparison

    is_normal = check_normality(sample_a) and check_normality(sample_b)

    try:
        if is_normal:
            statistic, p_value = sp_stats.ttest_ind(sample_a, sample_b, equal_var=False)
            test_used = "welch_ttest"
        else:
            statistic, p_value = sp_stats.mannwhitneyu(sample_a, sample_b, alternative="two-sided")
            test_used = "mann_whitney_u"
    except Exception as exc:
        comparison.warning = f"Ошибка статистического теста: {exc}"
        comparison.interpretation = interpret_result(pct_diff, None, metric, comparison.effect_size_label)
        return comparison

    comparison.test_used = test_used
    comparison.statistic = float(statistic)
    comparison.p_value = float(p_value)
    comparison.is_significant = bool(p_value < SIGNIFICANCE_LEVEL)
    comparison.interpretation = interpret_result(pct_diff, float(p_value), metric, comparison.effect_size_label)
    return comparison
