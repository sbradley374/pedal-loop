import Foundation
import PedalCore

@main enum Driver {
    static func main() async {
        do { try await run() }
        catch {
            FileHandle.standardError.write(Data("API smoke failed: \(error.localizedDescription)\n".utf8))
            exit(1)
        }
    }
    static func run() async throws {
        let env = ProcessInfo.processInfo.environment
        guard let address = env["PEDAL_SERVER_URL"] else { throw APIError.server("Set PEDAL_SERVER_URL and the STAGING_USER/STAGING_PASSWORD environment variables.") }
        let client = try APIClient(address: address, username: env["STAGING_USER"] ?? "", password: env["STAGING_PASSWORD"] ?? "")
        defer { client.close() }
        let info = try await client.info()
        guard let region = info.regions.first(where: { $0.label.contains("Burlington") }) else { throw APIError.server("Burlington fixture is required for this smoke test.") }
        var preferences = SearchRequest()
        preferences.regionID = region.id; preferences.lat = 44.4759; preferences.lon = -73.2121; preferences.miles = 5
        var job = try await client.submit(preferences)
        do {
            let deadline = Date().addingTimeInterval(90)
            while job.status == "running" || job.status == "queued" {
                guard Date() < deadline else { throw APIError.timedOut }
                try await Task.sleep(nanoseconds: 500_000_000)
                job = try await client.job(job.id)
            }
            guard job.status == "complete", let id = job.resultID else { throw APIError.server(job.error ?? "Search failed") }
            let result = try await client.result(id)
            guard result.isReal, !result.routes.isEmpty, result.routes.allSatisfy(\.isNavigable),
                  result.routes.allSatisfy({ !($0.navigationCues ?? []).isEmpty }) else { throw APIError.invalidResponse }
            for route in result.routes {
                var engine = NavigationEngine(route: route)
                let first = route.points[0]
                let now = Date().timeIntervalSince1970
                let update = engine.update(GPSFix(point: first, accuracy: 5, timestamp: now), now: now)
                guard update.state == .onRoute, update.progress < 1, (update.remaining ?? 0) > 1000 else { throw APIError.invalidResponse }
            }
            print("Swift HTTPS API smoke passed: catalog, search, \(result.routes.count) alternatives, cues, geometry, start matching and local GPX (\(result.routes[0].gpx().utf8.count) bytes).")
        } catch {
            try? await client.cancel(job.id)
            throw error
        }
    }
}
