import Foundation
import Combine
import CoreLocation
import AVFoundation
import UIKit
import PedalCore

@MainActor final class RideController: NSObject, ObservableObject, CLLocationManagerDelegate, AVSpeechSynthesizerDelegate {
    @Published var active: SavedRoute?
    @Published var recovery: RideRecovery?
    @Published var update: NavigationUpdate?
    @Published var position: CLLocation?
    @Published var paused = false
    @Published var simulating = false
    @Published var elapsed: TimeInterval = 0
    @Published var voice = true
    @Published var follow = true
    @Published var message: String?
    @Published var history = LocalFiles.read("history.json", as: [RideSummary].self) ?? []
    private let location = CLLocationManager()
    private let speech = AVSpeechSynthesizer()
    private var engine: NavigationEngine?
    private var timer: Timer?
    private var simulation: Task<Void, Never>?
    private var resumedAt: Date?
    private var accrued: TimeInterval = 0
    private var announced = Set<String>()
    private var lastFixAt: Date?
    private var lastPersistAt = Date.distantPast
    private var locationCallback: ((Point) -> Void)?
    private var resumeAfterPermission = false

    override init() {
        super.init()
        speech.delegate = self
        location.delegate = self
        location.activityType = .fitness
        location.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        location.distanceFilter = 3
        location.pausesLocationUpdatesAutomatically = false
        location.showsBackgroundLocationIndicator = true
        if let value = LocalFiles.read("active-ride.json", as: RideRecovery.self), value.saved.isValid { recovery = value }
    }
    var authorized: Bool { location.authorizationStatus == .authorizedAlways || location.authorizationStatus == .authorizedWhenInUse }
    var hasRide: Bool { active != nil }
    func locate(_ callback: @escaping (Point) -> Void) {
        guard !hasRide else { return }
        locationCallback = callback
        if authorized { location.requestLocation() }
        else if location.authorizationStatus == .notDetermined { location.requestWhenInUseAuthorization() }
        else { message = "Allow Location in iPhone Settings to use your current position."; locationCallback = nil }
    }
    func start(_ saved: SavedRoute, simulation: Bool = false) {
        guard active == nil, saved.isValid, saved.result.isReal || simulation else {
            message = "Only real-road routes can start GPS navigation."; return
        }
        active = saved; engine = NavigationEngine(route: saved.route)
        simulating = simulation; accrued = 0; elapsed = 0; update = nil; position = nil
        announced = []; follow = true; message = nil; paused = true
        recovery = nil
        resume()
    }
    func restore() {
        guard let recovery else { return }
        active = recovery.saved; engine = NavigationEngine(route: recovery.saved.route, checkpoint: recovery.checkpoint)
        accrued = recovery.elapsed; elapsed = accrued; paused = true; simulating = false
        update = nil; position = nil; self.recovery = nil
        message = "Ride restored paused. Return near your last route position, then tap Resume."
    }
    func discardRecovery() {
        do { try LocalFiles.remove("active-ride.json"); recovery = nil }
        catch { message = "Could not remove the recovery file." }
    }
    func pause() {
        guard hasRide else { return }
        resumeAfterPermission = false
        if let resumedAt { accrued += Date().timeIntervalSince(resumedAt) }
        resumedAt = nil; elapsed = accrued; paused = true
        location.stopUpdatingLocation(); location.allowsBackgroundLocationUpdates = false
        simulation?.cancel(); simulation = nil; timer?.invalidate(); timer = nil
        speech.stopSpeaking(at: .immediate); deactivateAudio()
        engine?.interrupt(); lastFixAt = nil
        UIApplication.shared.isIdleTimerDisabled = false
        persist()
    }
    func resume() {
        guard let active, paused else { return }
        if !simulating && !authorized {
            if location.authorizationStatus == .notDetermined {
                resumeAfterPermission = true
                location.requestWhenInUseAuthorization()
            }
            else { message = "Location permission is required. Enable Precise Location in Settings, then tap Resume." }
            return
        }
        resumeAfterPermission = false
        paused = false; resumedAt = Date(); message = nil; lastFixAt = nil; update = nil
        engine?.interrupt(); announced = []
        UIApplication.shared.isIdleTimerDisabled = true
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        if simulating { runSimulation(active.route) }
        else {
            location.allowsBackgroundLocationUpdates = true
            location.startUpdatingLocation()
            persist()
        }
    }
    func end() {
        guard active != nil else { return }
        let completed = update?.state == .arrived
        pause()
        if !simulating {
            var next = history
            next.insert(RideSummary(miles: (engine?.ridden ?? 0) / 1609.344, seconds: elapsed, completed: completed), at: 0)
            do { try LocalFiles.write(Array(next.prefix(30)), to: "history.json"); history = Array(next.prefix(30)) }
            catch { message = "Ride ended, but its summary could not be saved." }
        }
        do { try LocalFiles.remove("active-ride.json") }
        catch { message = "Ride ended, but its recovery file could not be removed." }
        active = nil; engine = nil; update = nil; position = nil; simulating = false; paused = false
    }
    func clearHistory() {
        do { try LocalFiles.remove("history.json"); history = [] }
        catch { message = "Could not delete ride history." }
    }
    func didEnterBackground() {
        // GPS rides continue through Core Location; simulations stop when hidden.
        if simulating { pause() } else { persist() }
    }
    private func tick() {
        elapsed = accrued + (resumedAt.map { Date().timeIntervalSince($0) } ?? 0)
        if !simulating, Date().timeIntervalSince(lastFixAt ?? resumedAt ?? Date()) > 15 {
            engine?.interrupt()
            update = NavigationUpdate(state: .weakGPS, speed: nil, ridden: engine?.ridden ?? 0,
                                      progress: engine?.progress ?? 0, remaining: nil, next: nil, distanceToCue: nil)
        }
        if Date().timeIntervalSince(lastPersistAt) > 5 { persist() }
    }
    private func consume(_ fix: GPSFix, location current: CLLocation) {
        guard hasRide, !paused, var engine else { return }
        let previous = update?.state
        let next = engine.update(fix, now: Date().timeIntervalSince1970)
        self.engine = engine
        guard next.state != .ignored else { return }
        update = next
        if next.state != .weakGPS { position = current; lastFixAt = Date() }
        if next.state == .offRoute && previous != .offRoute {
            say("Off route. Stop safely and check the map.")
        }
        if next.state == .onRoute, let cue = next.next, let distance = next.distanceToCue {
            let threshold = max(45, (next.speed ?? 4) * 12)
            let stage = distance < 20 ? "now" : "ahead"
            let key = "\(cue.coordinateIndex)-\(stage)"
            if distance <= threshold && !announced.contains(key) {
                announced.insert(key)
                say(stage == "now" ? cue.instruction : "In \(Int(distance / 5) * 5) meters, \(cue.instruction)")
            }
        }
        if next.state == .arrived && previous != .arrived { pause(); say("You have returned to the route start.") }
        if Date().timeIntervalSince(lastPersistAt) > 5 { persist() }
    }
    private func say(_ text: String) {
        guard voice else { return }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        do {
            let audio = AVAudioSession.sharedInstance()
            try audio.setCategory(.playback, mode: .voicePrompt, options: [.duckOthers, .interruptSpokenAudioAndMixWithOthers])
            try audio.setActive(true)
            speech.stopSpeaking(at: .immediate)
            let utterance = AVSpeechUtterance(string: text)
            utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
            speech.speak(utterance)
        } catch { message = "Audio unavailable; follow the on-screen cues." }
    }
    private func deactivateAudio() { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor [weak self] in
            guard let self, !self.speech.isSpeaking else { return }
            self.deactivateAudio()
        }
    }
    func silence() { if !voice { speech.stopSpeaking(at: .immediate); deactivateAudio() } }
    private func persist() {
        guard !simulating, let active, let engine else { return }
        do {
            try LocalFiles.write(RideRecovery(saved: active, checkpoint: engine.checkpoint,
                                             elapsed: elapsed, updatedAt: Date()), to: "active-ride.json")
            lastPersistAt = Date()
        } catch { message = "Ride recovery could not be saved; keep the app open." }
    }
    private func runSimulation(_ route: Route) {
        let points = route.points
        // Sample every ~8 m so route geometry density does not change replay behavior.
        simulation = Task { [weak self] in
            guard let self else { return }
            var along = 0.0
            for (a, b) in zip(points, points.dropFirst()) {
                let length = a.distance(to: b), steps = max(1, Int(ceil(length / 8)))
                for n in 0..<steps {
                    let t = Double(n) / Double(steps)
                    guard !Task.isCancelled else { return }
                    if along + length * t + 8 < (self.engine?.progress ?? 0) { continue }
                    let p = Point(a.latitude + (b.latitude - a.latitude) * t, a.longitude + (b.longitude - a.longitude) * t)
                    let date = Date()
                    self.consume(GPSFix(point: p, accuracy: 5, timestamp: date.timeIntervalSince1970, speed: 8),
                                 location: CLLocation(latitude: p.latitude, longitude: p.longitude))
                    try? await Task.sleep(nanoseconds: 350_000_000)
                }
                along += length
            }
            if let end = points.last, !Task.isCancelled {
                self.consume(GPSFix(point: end, accuracy: 5, timestamp: Date().timeIntervalSince1970, speed: 0),
                             location: CLLocation(latitude: end.latitude, longitude: end.longitude))
            }
        }
    }
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor [weak self] in self?.authorizationChanged() }
    }
    private func authorizationChanged() {
        if authorized {
            if locationCallback != nil { location.requestLocation() }
            if resumeAfterPermission && active != nil && paused { resume() }
        } else if location.authorizationStatus == .denied || location.authorizationStatus == .restricted {
            if hasRide { pause() }
            locationCallback = nil; message = "Location access is off. You can still plan routes and use the route preview."
        }
    }
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        Task { @MainActor [weak self] in self?.receivedLocations(locations) }
    }
    private func receivedLocations(_ locations: [CLLocation]) {
        guard let current = locations.last else { return }
        let point = Point(current.coordinate.latitude, current.coordinate.longitude)
        if let callback = locationCallback {
            guard current.horizontalAccuracy >= 0, current.horizontalAccuracy <= 40,
                  abs(current.timestamp.timeIntervalSinceNow) < 15 else {
                locationCallback = nil; message = "Location is too imprecise. Enable Precise Location or choose a start on the map."; return
            }
            locationCallback = nil; callback(point)
        }
        guard !simulating else { return }
        guard let resumedAt, current.timestamp >= resumedAt else { return }
        consume(GPSFix(point: point, accuracy: current.horizontalAccuracy,
                       timestamp: current.timestamp.timeIntervalSince1970, speed: current.speed), location: current)
    }
    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor [weak self] in self?.locationFailed() }
    }
    private func locationFailed() {
        guard locationCallback != nil || (hasRide && !paused && !simulating) else { return }
        locationCallback = nil
        engine?.interrupt()
        update = NavigationUpdate(state: .weakGPS, speed: nil, ridden: engine?.ridden ?? 0,
                                  progress: engine?.progress ?? 0, remaining: nil, next: nil, distanceToCue: nil)
        message = "Waiting for GPS. Check Location permission and move into open sky."
    }
}
