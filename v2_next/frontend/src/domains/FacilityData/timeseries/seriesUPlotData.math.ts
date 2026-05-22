import type uPlot from 'uplot';
import type { TimeSeriesKey, TimeSeriesMeta } from './seriesCatalog';
import type { SeriesFrame } from './seriesDataFrames';
import type { SeriesFrameField } from './seriesDataFrames.types';

export const DEFAULT_CHART_PIXEL_WIDTH = 800;

const MIN_RENDER_POINTS = 300;
const MAX_RENDER_POINTS = 4000;
const RENDER_POINTS_PER_PIXEL = 2;

export type TimeWindowRange = [number, number];

const getFieldBySeriesKey = (timeSeriesAllFrame: SeriesFrame, key: TimeSeriesKey): SeriesFrameField => {
  const field = timeSeriesAllFrame.fields.find((candidate) => candidate.name === key);

  if (field === undefined) {
    throw new Error(`Time series field was not found: key=${key}`);
  }

  return field;
};

export const buildRenderPointLimit = (chartPixelWidth: number): number => {
  const finiteWidth = Number.isFinite(chartPixelWidth) && chartPixelWidth > 0 ? chartPixelWidth : DEFAULT_CHART_PIXEL_WIDTH;
  const widthLimit = Math.floor(finiteWidth * RENDER_POINTS_PER_PIXEL);
  return Math.max(MIN_RENDER_POINTS, Math.min(MAX_RENDER_POINTS, widthLimit));
};

const getNumericDataSeries = (uPlotData: uPlot.AlignedData): Array<Array<number | null>> => {
  const dataSeries: Array<Array<number | null>> = [];

  for (let seriesIndex = 1; seriesIndex < uPlotData.length; seriesIndex += 1) {
    const values = uPlotData[seriesIndex] as Array<number | null>;

    if (values.some((value) => typeof value === 'number' && Number.isFinite(value))) {
      dataSeries.push(values);
    }
  }

  return dataSeries;
};

const buildBucketExtremaIndices = (
  dataSeries: Array<Array<number | null>>,
  startIndex: number,
  endIndex: number
): number[] => {
  const selectedIndices = new Set<number>();

  dataSeries.forEach((values) => {
    let minIndex = -1;
    let maxIndex = -1;
    let minValue = Number.POSITIVE_INFINITY;
    let maxValue = Number.NEGATIVE_INFINITY;

    for (let index = startIndex; index < endIndex; index += 1) {
      const value = values[index];

      if (typeof value !== 'number' || !Number.isFinite(value)) {
        continue;
      }

      if (value < minValue) {
        minValue = value;
        minIndex = index;
      }

      if (value > maxValue) {
        maxValue = value;
        maxIndex = index;
      }
    }

    if (minIndex !== -1) {
      selectedIndices.add(minIndex);
    }

    if (maxIndex !== -1) {
      selectedIndices.add(maxIndex);
    }
  });

  if (selectedIndices.size === 0) {
    return [Math.floor((startIndex + endIndex - 1) / 2)];
  }

  return Array.from(selectedIndices).sort((left, right) => left - right);
};

const buildEvenlySpacedIndices = (pointCount: number, maxPoints: number): number[] => {
  const step = pointCount <= 1 ? 1 : (pointCount - 1) / (maxPoints - 1);
  const selectedIndices = new Set<number>([0, pointCount - 1]);

  for (let index = 1; index < maxPoints - 1; index += 1) {
    selectedIndices.add(Math.round(index * step));
  }

  return Array.from(selectedIndices).sort((left, right) => left - right);
};

const trimSortedIndicesToLimit = (sortedIndices: number[], maxPoints: number): number[] => {
  if (sortedIndices.length <= maxPoints) {
    return sortedIndices;
  }

  if (maxPoints <= 0) {
    return [];
  }

  if (maxPoints === 1) {
    return [sortedIndices[sortedIndices.length - 1]];
  }

  const firstIndex = sortedIndices[0];
  const lastIndex = sortedIndices[sortedIndices.length - 1];
  const interiorLimit = maxPoints - 2;

  return [
    firstIndex,
    ...sortedIndices.slice(1, -1).slice(0, interiorLimit),
    lastIndex,
  ];
};

const buildExtremaPreservingIndices = (
  pointCount: number,
  maxPoints: number,
  dataSeries: Array<Array<number | null>>
): number[] => {
  const maxIndicesPerBucket = Math.max(1, dataSeries.length * 2);
  const bucketCount = Math.max(1, Math.floor((maxPoints - 2) / maxIndicesPerBucket));
  const bucketSize = (pointCount - 2) / bucketCount;
  const selectedIndices = new Set<number>([0, pointCount - 1]);

  for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
    const startIndex = Math.max(1, Math.floor(1 + bucketIndex * bucketSize));
    const endIndex = Math.min(pointCount - 1, Math.floor(1 + (bucketIndex + 1) * bucketSize));
    const safeEndIndex = Math.max(startIndex + 1, endIndex);

    buildBucketExtremaIndices(dataSeries, startIndex, safeEndIndex).forEach((index) => {
      selectedIndices.add(index);
    });
  }

  const sortedIndices = Array.from(selectedIndices).sort((left, right) => left - right);

  return trimSortedIndicesToLimit(sortedIndices, maxPoints);
};

export const buildDownsampledIndices = (uPlotData: uPlot.AlignedData, maxPoints: number): number[] => {
  const timeValues = uPlotData[0];
  const pointCount = timeValues.length;

  if (pointCount <= maxPoints) {
    return Array.from(timeValues, (_value, index) => index);
  }

  const dataSeries = getNumericDataSeries(uPlotData);

  if (dataSeries.length === 0) {
    return buildEvenlySpacedIndices(pointCount, maxPoints);
  }

  return buildExtremaPreservingIndices(pointCount, maxPoints, dataSeries);
};

export const downsampleUPlotData = (uPlotData: uPlot.AlignedData, maxPoints: number): uPlot.AlignedData => {
  const selectedIndices = buildDownsampledIndices(uPlotData, maxPoints);

  if (selectedIndices.length === uPlotData[0].length) {
    return uPlotData;
  }

  return uPlotData.map((values) => selectedIndices.map((index) => values[index] ?? null)) as uPlot.AlignedData;
};

const assertAlignedUPlotData = (uPlotData: uPlot.AlignedData): void => {
  const pointCount = uPlotData[0].length;

  uPlotData.forEach((values, seriesIndex) => {
    if (values.length !== pointCount) {
      throw new Error(`Time series aligned data length mismatch: seriesIndex=${seriesIndex}, expected=${pointCount}, actual=${values.length}.`);
    }
  });
};

const isChronologicalUPlotData = (uPlotData: uPlot.AlignedData): boolean => {
  const timeValues = uPlotData[0];

  for (let index = 1; index < timeValues.length; index += 1) {
    const previousValue = timeValues[index - 1];
    const currentValue = timeValues[index];

    if (typeof previousValue === 'number' && typeof currentValue === 'number' && currentValue < previousValue) {
      return false;
    }
  }

  return true;
};

export const sortUPlotDataByTime = (uPlotData: uPlot.AlignedData): uPlot.AlignedData => {
  if (isChronologicalUPlotData(uPlotData)) {
    return uPlotData;
  }

  const sortedIndices = Array.from(uPlotData[0], (_value, index) => index).sort((leftIndex, rightIndex) => {
    const leftValue = uPlotData[0][leftIndex];
    const rightValue = uPlotData[0][rightIndex];
    const leftTime = typeof leftValue === 'number' && Number.isFinite(leftValue) ? leftValue : Number.POSITIVE_INFINITY;
    const rightTime = typeof rightValue === 'number' && Number.isFinite(rightValue) ? rightValue : Number.POSITIVE_INFINITY;

    if (leftTime === rightTime) {
      return leftIndex - rightIndex;
    }

    return leftTime - rightTime;
  });

  return uPlotData.map((values) => sortedIndices.map((index) => values[index] ?? null)) as uPlot.AlignedData;
};

export const buildVisibleUPlotData = (
  timeSeriesAllFrame: SeriesFrame,
  metas: readonly TimeSeriesMeta[],
  chartPixelWidth: number
): uPlot.AlignedData => {
  const timeField = timeSeriesAllFrame.fields[0];

  if (timeField === undefined || timeField.type !== 'time') {
    throw new Error('Time series frame must include a time field at index 0.');
  }

  const projectedData = [
    timeField.values.map((value) => (value ?? 0) / 1000),
    ...metas.map((meta) => getFieldBySeriesKey(timeSeriesAllFrame, meta.key).values),
  ] as uPlot.AlignedData;

  assertAlignedUPlotData(projectedData);

  return downsampleUPlotData(sortUPlotDataByTime(projectedData), buildRenderPointLimit(chartPixelWidth));
};

export const buildTimeWindowRange = (
  uPlotData: uPlot.AlignedData | null,
  seriesWindowMin: number
): TimeWindowRange | null => {
  const timeValues = uPlotData?.[0] as ArrayLike<number | null> | undefined;
  const windowSec = seriesWindowMin * 60;

  if (timeValues === undefined || timeValues.length === 0 || !Number.isFinite(windowSec) || windowSec <= 0) {
    return null;
  }

  const latestValue = timeValues[timeValues.length - 1];

  if (typeof latestValue !== 'number' || !Number.isFinite(latestValue)) {
    return null;
  }

  return [latestValue - windowSec, latestValue];
};
