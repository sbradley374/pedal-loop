import Testing
import Foundation
@testable import PedalCore

struct NavigationTests {
    private var route: Route {
        Route(points: [Point(40, -105), Point(40.001, -105), Point(40.001, -104.999), Point(40, -104.999), Point(40, -105)],
              distanceMiles: 0.25, cues: [.init(distanceM: 111, coordinateIndex: 1, instruction: "Turn right"),
                                       .init(distanceM: 390, coordinateIndex: 4, instruction: "Return to start")])
    }
    private func fix(_ lat: Double = 40, _ lon: Double = -105, _ time: Double = 1000, accuracy: Double = 5, speed: Double? = 4) -> GPSFix {
        GPSFix(point: Point(lat, lon), accuracy: accuracy, timestamp: time, speed: speed)
    }
    @Test func testClosedLoopStartsAtStartNotFinish() {
        var engine = NavigationEngine(route: route)
        let value = engine.update(fix(), now: 1000)
        expectEqual(value.state, .onRoute)
        expectEqual(value.progress, 0)
        expectGreater(value.remaining ?? 0, 350)
        expectEqual(value.next?.instruction, "Turn right")
    }
    @Test func testProgressAndMileage() {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        let value = engine.update(fix(40.0002, -105, 1005), now: 1005)
        expectEqual(value.state, .onRoute)
        expectEqual(value.ridden, 22.24, accuracy: 0.2)
        expectEqual(value.progress, 22.24, accuracy: 0.2)
        expectEqual(value.speed, 4)
    }
    @Test func testBadFixesDoNotAdvance() {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        expectEqual(engine.update(fix(40.01, -105, 1001), now: 1001).state, .weakGPS)
        expectEqual(engine.update(fix(40, -105, 1002, accuracy: 100), now: 1002).state, .weakGPS)
        expectEqual(engine.update(fix(), now: 1020).state, .weakGPS)
        expectEqual(engine.update(fix(.nan), now: 1000).state, .weakGPS)
        expectEqual(engine.update(fix(40, -105, 1100), now: 1000).state, .weakGPS)
        expectEqual(engine.progress, 0)
    }
    @Test func testDuplicateAndOutOfOrderFixesIgnored() {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        expectEqual(engine.update(fix(), now: 1000).state, .ignored)
        expectEqual(engine.update(fix(40, -105, 999), now: 1000).state, .ignored)
    }
    @Test func testStartingAwayFromStartDoesNotActivate() {
        var engine = NavigationEngine(route: route)
        expectEqual(engine.update(fix(40.001, -104.999), now: 1000).state, .waiting)
        expectFalse(engine.started)
    }
    @Test func testStationaryJitterDoesNotAccumulate() {
        var engine = NavigationEngine(route: route)
        for i in 0..<10 { _ = engine.update(fix(40 + Double(i % 2) * 0.00001, -105, 1000 + Double(i)), now: 1000 + Double(i)) }
        expectEqual(engine.ridden, 0)
    }
    @Test func testPauseAndSignalGapDoNotBridgeMileage() {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        engine.interrupt()
        expectEqual(engine.update(fix(40.0004, -105, 1030), now: 1030).ridden, 0)
        expectEqual(engine.update(fix(40.0006, -105, 1060), now: 1060).ridden, 0)
    }
    @Test func testOffRouteSuppressesCues() {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        let value = engine.update(fix(39.9995, -105, 1005), now: 1005)
        expectEqual(value.state, .offRoute)
        expectNil(value.next); expectNil(value.remaining)
    }
    @Test func testRecoveryDoesNotBridgeMileage() throws {
        var engine = NavigationEngine(route: route)
        _ = engine.update(fix(), now: 1000)
        _ = engine.update(fix(40.0003, -105, 1005), now: 1005)
        let data = try JSONEncoder().encode(engine.checkpoint)
        var recovered = NavigationEngine(route: route, checkpoint: try JSONDecoder().decode(NavigationCheckpoint.self, from: data))
        let value = recovered.update(fix(40.0005, -105, 1100), now: 1100)
        expectEqual(value.ridden, engine.ridden)
        expectGreater(value.progress, engine.progress)
    }
    @Test func testFullLoopOnlyArrivesAfterTraversal() {
        var engine = NavigationEngine(route: route), time = 1000.0
        var value = engine.update(fix(), now: time)
        for (a, b) in zip(route.points, route.points.dropFirst()) {
            for step in 1...10 {
                time += 3
                let t = Double(step) / 10
                value = engine.update(fix(a.latitude + (b.latitude - a.latitude) * t,
                                         a.longitude + (b.longitude - a.longitude) * t, time), now: time)
            }
        }
        expectEqual(value.state, .arrived)
        expectGreater(value.ridden, 350)
        expectLess(value.remaining ?? 999, 20)
    }
    @Test func testInvalidGeometryIsRejected() {
        let invalid = Route(points: [Point(.nan, 0)], distanceMiles: 2)
        expectFalse(invalid.isNavigable)
        var engine = NavigationEngine(route: invalid)
        expectEqual(engine.update(fix(), now: 1000).state, .weakGPS)
    }
    @Test func testFutureCrossingCannotSkipRoute() {
        let crossing = Route(points: [Point(40, -105), Point(40.002, -105), Point(40.002, -104.998),
                                     Point(40, -105), Point(39.998, -105), Point(40, -105)], distanceMiles: 1)
        var engine = NavigationEngine(route: crossing)
        let value = engine.update(fix(), now: 1000)
        expectEqual(value.progress, 0)
        expectGreater(value.remaining ?? 0, 800)
    }
}
