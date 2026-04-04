"""
Статистические функции для сравнительного анализа тестов
"""
import math
from typing import Dict, List, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover - зависит от окружения
    np = None

try:
    from scipy import stats
except ImportError:  # pragma: no cover - зависит от окружения
    stats = None

from backend.comparison.schemas import DescriptiveStats, PairwiseComparison


MIN_SAMPLE_SIZE_FOR_TEST = 10
NORMALITY_SAMPLE_LIMIT = 5000
SIGNIFICANCE_LEVEL = 0.05


def _ensure_dependencies_available():
    """Проверить, что аналитические зависимости доступны"""
    if np is None or stats is None:
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

    return DescriptiveStats(
        count=len(clean_data),
        mean=float(np.mean(clean_data)),
        median=float(np.median(clean_data)),
        std=std_value,
        min=float(np.min(clean_data)),
        max=float(np.max(clean_data)),
        p50=float(np.percentile(clean_data, 50)),
        p95=float(np.percentile(clean_data, 95)),
        p99=float(np.percentile(clean_data, 99)),
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
        _, p_value = stats.shapiro(sample)
    except Exception:
        return False

    return bool(p_value > SIGNIFICANCE_LEVEL)


def safe_pct_difference(baseline: float, compared: float) -> Optional[float]:
    """Безопасно рассчитать процентное отличие от baseline"""
    if baseline == 0:
        return None
    return ((compared - baseline) / baseline) * 100.0


def interpret_result(pct_diff: Optional[float], p_value: Optional[float], metric: str) -> str:
    """Сформировать текстовую интерпретацию результата"""
    if p_value is None:
        return "Недостаточно данных для статистического теста"

    if p_value >= SIGNIFICANCE_LEVEL:
        return "Разница статистически незначима"

    if pct_diff is None:
        return "Невозможно рассчитать процентное отличие относительно baseline"

    if metric == "latency_ms":
        if pct_diff > 0:
            return f"Сравниваемый тест медленнее на {abs(pct_diff):.1f}% (p={p_value:.4f})"
        return f"Сравниваемый тест быстрее на {abs(pct_diff):.1f}% (p={p_value:.4f})"

    if pct_diff > 0:
        return f"Сравниваемый тест показывает прирост на {abs(pct_diff):.1f}% (p={p_value:.4f})"
    return f"Сравниваемый тест показывает снижение на {abs(pct_diff):.1f}% (p={p_value:.4f})"


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

    if len(sample_a) < MIN_SAMPLE_SIZE_FOR_TEST or len(sample_b) < MIN_SAMPLE_SIZE_FOR_TEST:
        comparison.warning = (
            f"Недостаточно данных для статистического теста: n_baseline={len(sample_a)}, n_compared={len(sample_b)}"
        )
        comparison.interpretation = interpret_result(pct_diff, None, metric)
        return comparison

    is_normal = check_normality(sample_a) and check_normality(sample_b)

    try:
        if is_normal:
            statistic, p_value = stats.ttest_ind(sample_a, sample_b, equal_var=False)
            test_used = "welch_ttest"
        else:
            statistic, p_value = stats.mannwhitneyu(sample_a, sample_b, alternative="two-sided")
            test_used = "mann_whitney_u"
    except Exception as exc:
        comparison.warning = f"Ошибка статистического теста: {exc}"
        comparison.interpretation = interpret_result(pct_diff, None, metric)
        return comparison

    comparison.test_used = test_used
    comparison.statistic = float(statistic)
    comparison.p_value = float(p_value)
    comparison.is_significant = bool(p_value < SIGNIFICANCE_LEVEL)
    comparison.interpretation = interpret_result(pct_diff, float(p_value), metric)
    return comparison
