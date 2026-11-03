import Foundation
import Combine
import SwiftUI
import PedalCore

@MainActor final class PlannerModel: ObservableObject {
    @Published var credentials = SecureSettings.load()
    @Published var preferences = SearchRequest()
    @Published var regions: [Region] = []
    @Published var result: RouteResult?
    @Published var routeIndex = 0
    @Published var saved = (LocalFiles.read("routes.json", as: [SavedRoute].self) ?? []).filter(\.isValid)
    @Published var busy = false
    @Published var status = "Connect your route server to begin."
    @Published var error: String?
    @Published var connected = false
    @Published var connecting = false
    private var task: Task<Void, Never>?
    private var client: APIClient?
    private var jobID: String?
    private var generation = UUID()

    var selected: SavedRoute? {
        guard let result, result.routes.indices.contains(routeIndex) else { return nil }
        return SavedRoute(result: result, index: routeIndex)
    }
    func configure(_ settings: ServerCredentials) async {
        cancel()
        let token = UUID(); generation = token
        connecting = true; connected = false; regions = []
        defer { if generation == token { connecting = false } }
        do {
            let next = try APIClient(address: settings.address, username: settings.username, password: settings.password)
            client?.close(); client = next
            let info = try await next.info()
            guard generation == token else { return }
            try SecureSettings.save(settings)
            credentials = settings; regions = info.regions; connected = true
            if let region = regions.first(where: { $0.id == info.activeRegion }) ?? regions.first { choose(region) }
            status = "Connected · \(regions.count) cached regions"
        } catch {
            guard generation == token else { return }
            self.error = error.localizedDescription; status = "Connection failed"
        }
    }
    func choose(_ region: Region) {
        preferences.regionID = region.id
        if let point = region.point { preferences.lat = point.latitude; preferences.lon = point.longitude }
        result = nil; routeIndex = 0
    }
    func useLocation(_ point: Point) {
        guard point.isValid else { return }
        if let closest = regions.filter({ region in
            guard let center = region.point, let radius = region.radiusM else { return false }
            return center.distance(to: point) < radius
        }).min(by: { $0.point!.distance(to: point) < $1.point!.distance(to: point) }) {
            preferences.regionID = closest.id
        }
        preferences.lat = point.latitude; preferences.lon = point.longitude
        result = nil
    }
    func search() {
        guard connected, let client else { error = "Connect to your route server first."; return }
        cancel()
        let token = UUID(); generation = token
        let request = preferences
        busy = true; error = nil; result = nil; status = "Finding your loop…"
        task = Task {
            var submittedID: String?
            do {
                var job = try await client.submit(request)
                submittedID = job.id
                guard generation == token, !Task.isCancelled else {
                    try? await client.cancel(job.id); return
                }
                jobID = job.id
                let deadline = Date().addingTimeInterval(120)
                while job.status == "queued" || job.status == "running" {
                    guard Date() < deadline else { throw APIError.timedOut }
                    status = job.status == "queued" ? "Waiting for the route engine…" : "Searching roads and climbing options…"
                    try await Task.sleep(nanoseconds: 700_000_000)
                    job = try await client.job(job.id)
                    try Task.checkCancellation()
                }
                guard job.status == "complete", let id = job.resultID else {
                    throw APIError.server(job.error ?? "Search ended without a route. Try different preferences.")
                }
                let found = try await client.result(id)
                guard generation == token, !Task.isCancelled else { return }
                guard !found.routes.isEmpty, found.routes.allSatisfy(\.isNavigable) else { throw APIError.invalidResponse }
                result = found; routeIndex = 0; status = "\(found.routes.count) route options"
            } catch {
                if let submittedID {
                    // Use a separate task: the search task may already be cancelled.
                    Task { try? await client.cancel(submittedID) }
                }
                guard generation == token, !Task.isCancelled else { return }
                self.error = error.localizedDescription; status = "Search stopped"
            }
            if generation == token { busy = false; jobID = nil; task = nil }
        }
    }
    func cancel() {
        generation = UUID(); task?.cancel(); task = nil
        if let id = jobID, let client { Task { try? await client.cancel(id) } }
        jobID = nil; busy = false; connecting = false
        status = "Search cancelled"
    }
    func saveSelected() {
        guard let selected else { return }
        var next = saved.filter { $0.id != selected.id }
        next.insert(selected, at: 0); next = Array(next.prefix(20))
        do { try LocalFiles.write(next, to: "routes.json"); saved = next; status = "Route downloaded to this iPhone" }
        catch { self.error = "Could not save the route: \(error.localizedDescription)" }
    }
    func delete(_ offsets: IndexSet) {
        var next = saved; next.remove(atOffsets: offsets)
        do { try LocalFiles.write(next, to: "routes.json"); saved = next }
        catch { self.error = error.localizedDescription }
    }
    func open(_ saved: SavedRoute) { cancel(); result = saved.result; routeIndex = saved.index; status = "Downloaded route" }
}
