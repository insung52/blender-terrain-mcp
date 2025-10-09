// Ramer-Douglas-Peucker algorithm
// Simplifies a path by reducing the number of points while preserving shape

type Point = [number, number];

/**
 * Calculate perpendicular distance from point to line segment
 */
function perpendicularDistance(point: Point, lineStart: Point, lineEnd: Point): number {
  const [x, y] = point;
  const [x1, y1] = lineStart;
  const [x2, y2] = lineEnd;

  const dx = x2 - x1;
  const dy = y2 - y1;

  // Line segment length squared
  const lengthSquared = dx * dx + dy * dy;

  if (lengthSquared === 0) {
    // Line start and end are the same point
    return Math.sqrt((x - x1) ** 2 + (y - y1) ** 2);
  }

  // Calculate perpendicular distance
  const numerator = Math.abs(dy * x - dx * y + x2 * y1 - y2 * x1);
  return numerator / Math.sqrt(lengthSquared);
}

/**
 * Ramer-Douglas-Peucker algorithm implementation
 * @param points - Array of points [x, y]
 * @param epsilon - Tolerance (higher = more simplification, lower = more detail)
 * @returns Simplified array of points
 */
export function simplifyPath(points: Point[], epsilon: number = 5.0): Point[] {
  if (points.length <= 2) {
    return points;
  }

  // Find the point with maximum distance from line between first and last
  let maxDistance = 0;
  let maxIndex = 0;

  const first = points[0];
  const last = points[points.length - 1];

  for (let i = 1; i < points.length - 1; i++) {
    const distance = perpendicularDistance(points[i], first, last);
    if (distance > maxDistance) {
      maxDistance = distance;
      maxIndex = i;
    }
  }

  // If max distance is greater than epsilon, recursively simplify
  if (maxDistance > epsilon) {
    // Recursive call on left and right segments
    const leftSegment = simplifyPath(points.slice(0, maxIndex + 1), epsilon);
    const rightSegment = simplifyPath(points.slice(maxIndex), epsilon);

    // Combine results (remove duplicate middle point)
    return [...leftSegment.slice(0, -1), ...rightSegment];
  } else {
    // Max distance is within tolerance, return just endpoints
    return [first, last];
  }
}

/**
 * Alternative: Simple distance-based thinning
 * Keeps points that are at least minDistance apart
 */
export function thinByDistance(points: Point[], minDistance: number = 10): Point[] {
  if (points.length === 0) return [];

  const result: Point[] = [points[0]];
  let lastPoint = points[0];

  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = lastPoint;
    const [x2, y2] = points[i];
    const distance = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);

    if (distance >= minDistance) {
      result.push(points[i]);
      lastPoint = points[i];
    }
  }

  // Always include last point
  if (result[result.length - 1] !== points[points.length - 1]) {
    result.push(points[points.length - 1]);
  }

  return result;
}

/**
 * Hybrid approach: First thin by distance, then simplify with RDP
 * Recommended for best results
 */
export function simplifyDrawnPath(
  points: Point[],
  options: {
    minDistance?: number;
    epsilon?: number;
    maxPoints?: number;
  } = {}
): Point[] {
  const { minDistance = 5, epsilon = 3, maxPoints = 20 } = options;

  // Step 1: Remove points that are too close together
  let simplified = thinByDistance(points, minDistance);

  // Step 2: Apply RDP algorithm
  simplified = simplifyPath(simplified, epsilon);

  // Step 3: If still too many points, increase epsilon and try again
  let currentEpsilon = epsilon;
  while (simplified.length > maxPoints && currentEpsilon < 50) {
    currentEpsilon *= 1.5;
    simplified = simplifyPath(points, currentEpsilon);
  }

  return simplified;
}
