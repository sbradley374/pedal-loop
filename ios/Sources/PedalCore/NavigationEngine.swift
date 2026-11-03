import Foundation

public struct GPSFix: Sendable {
    public var point: Point
    public var accuracy: Double
    public var timestamp: TimeInterval
    public var speed: Double?
    public init(point: Point, accuracy: Double, timestamp: TimeInterval, speed: Double? = nil) {
        self.point = point; self.accuracy = accuracy; self.timestamp = timestamp; self.speed = speed
    }
}
public enum RideState: String, Codable, Sendable { case waiting, onRoute, offRoute, weakGPS, arrived, ignored }
public struct NavigationUpdate: Sendable {
    public var state: RideState
    public var speed: Double?
    public var ridden: Double
    public var progress: Double
    public var remaining: Double?
    public var next: Cue?
    public var distanceToCue: Double?
    public init(state: RideState, speed: Double?, ridden: Double, progress: Double, remaining: Double?, next: Cue?, distanceToCue: Double?) {
        self.state = state; self.speed = speed; self.ridden = ridden; self.progress = progress
        self.remaining = remaining; self.next = next; self.distanceToCue = distanceToCue
    }
}
public struct NavigationCheckpoint: Codable, Sendable {
    public var progress: Double
    public var ridden: Double
    public var started: Bool
}

/// Bounded matching deliberately refuses ambiguous jumps to later legs of a loop.
/// It is a beta route follower, not road-network map matching or a rerouting engine.
public struct NavigationEngine {
    public let points: [Point]
    public let cumulative: [Double]
    public let cues: [Cue]
    public var total: Double { cumulative.last ?? 0 }
    public private(set) var progress = 0.0
    public private(set) var ridden = 0.0
    public private(set) var started = false
    private var last: GPSFix?
    private var anchor: GPSFix?
    public init(route: Route, checkpoint: NavigationCheckpoint? = nil) {
        points = route.isNavigable ? route.points : []
        var distances = [0.0]
        for (a, b) in zip(points, points.dropFirst()) { distances.append(distances.last! + a.distance(to: b)) }
        cumulative = distances
        // Use geometry indices rather than rounding differences in server edge distances.
        cues = (route.navigationCues ?? []).compactMap { cue in
            guard distances.indices.contains(cue.coordinateIndex), !cue.instruction.isEmpty else { return nil }
            return Cue(distanceM: distances[cue.coordinateIndex], coordinateIndex: cue.coordinateIndex, instruction: cue.instruction)
        }.sorted { $0.distanceM < $1.distanceM }
        if let checkpoint, checkpoint.progress.isFinite, checkpoint.ridden.isFinite {
            progress = max(0, min(distances.last ?? 0, checkpoint.progress))
            ridden = max(0, checkpoint.ridden); started = checkpoint.started
        }
    }
    public var checkpoint: NavigationCheckpoint { .init(progress: progress, ridden: ridden, started: started) }
    public mutating func interrupt() { last = nil; anchor = nil }
    private func output(_ state: RideState, speed: Double? = nil, matched: Bool = false) -> NavigationUpdate {
        let next = matched ? cues.first { $0.distanceM > 0 && $0.distanceM >= progress - 5 } : nil
        return NavigationUpdate(state: state, speed: speed, ridden: ridden, progress: progress,
                                remaining: matched ? max(0, total - progress) : nil, next: next,
                                distanceToCue: next.map { max(0, $0.distanceM - progress) })
    }
    public mutating func update(_ fix: GPSFix, now: TimeInterval) -> NavigationUpdate {
        guard points.count >= 2, fix.point.isValid, fix.accuracy.isFinite, fix.timestamp.isFinite,
              fix.accuracy >= 0, fix.accuracy <= 40, now - fix.timestamp <= 15, fix.timestamp <= now + 1 else {
            interrupt(); return output(.weakGPS)
        }
        if let last, fix.timestamp <= last.timestamp { return output(.ignored) }
        let dt = last.map { fix.timestamp - $0.timestamp } ?? 0
        if let last, dt > 0, dt <= 15,
           last.point.distance(to: fix.point) > 35 * dt + fix.accuracy + last.accuracy {
            return output(.weakGPS)
        }
        guard started || fix.point.distance(to: points[0]) <= 60 else { return output(.waiting) }
        started = true
        var speed = fix.speed.flatMap { $0.isFinite && $0 >= 0 && $0 <= 35 ? $0 : nil }
        if let anchor, dt > 0, dt <= 15, fix.timestamp - anchor.timestamp <= 15 {
            let traveled = anchor.point.distance(to: fix.point)
            if traveled >= max(6, fix.accuracy * 0.75) {
                ridden += traveled
                speed = speed ?? traveled / (fix.timestamp - anchor.timestamp)
                self.anchor = fix
            }
        } else { anchor = fix }
        last = fix
        let forward = max(75, min(15, dt) * 25)
        let scaleY = 6_371_000.0 * .pi / 180
        let scaleX = scaleY * cos(fix.point.latitude * .pi / 180)
        var best: (along: Double, away: Double, score: Double)?
        for i in 0..<(points.count - 1) {
            let start = cumulative[i], length = cumulative[i + 1] - start
            guard length > 0, start <= progress + forward, start + length >= progress - 30 else { continue }
            let a = points[i], b = points[i + 1]
            let ax = (a.longitude - fix.point.longitude) * scaleX, ay = (a.latitude - fix.point.latitude) * scaleY
            let dx = (b.longitude - a.longitude) * scaleX, dy = (b.latitude - a.latitude) * scaleY
            let denominator = dx * dx + dy * dy
            guard denominator > 0 else { continue }
            let t = max(0, min(1, -(ax * dx + ay * dy) / denominator))
            let along = start + t * length
            guard along <= progress + forward, along >= progress - 30 else { continue }
            let away = hypot(ax + t * dx, ay + t * dy)
            let score = away + abs(along - progress) * 0.02
            if best == nil || score < best!.score { best = (along, away, score) }
        }
        guard let best, best.away <= max(35, fix.accuracy * 1.5) else { return output(.offRoute, speed: speed) }
        progress = max(progress, best.along)
        return output(total - progress < 20 ? .arrived : .onRoute, speed: speed, matched: true)
    }
}
