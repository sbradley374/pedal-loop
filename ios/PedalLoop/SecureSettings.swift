import Foundation
import Security
import PedalCore

struct ServerCredentials: Codable {
    var address: String
    var username: String
    var password: String
    static let empty = ServerCredentials(address: "", username: "beta", password: "")
}
enum SecureSettings {
    private static let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "PedalLoop.Server",
        kSecAttrAccount as String: "beta"
    ]
    static func load() -> ServerCredentials {
        var lookup = query
        lookup[kSecReturnData as String] = true
        lookup[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(lookup as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let settings = try? JSONDecoder().decode(ServerCredentials.self, from: data) else { return .empty }
        return settings
    }
    static func save(_ value: ServerCredentials) throws {
        let data = try JSONEncoder().encode(value)
        let attributes: [String: Any] = [kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
        }
        guard status == errSecSuccess else {
            throw APIError.server("Could not save server settings to Keychain (\(status)).")
        }
    }
}

struct SavedRoute: Codable, Identifiable, Equatable {
    var result: RouteResult
    var index: Int
    var savedAt = Date()
    var id: String { "\(result.id)-\(index)" }
    var route: Route { result.routes[index] }
    var isValid: Bool { result.routes.indices.contains(index) && result.routes[index].isNavigable }
}
struct RideRecovery: Codable {
    var saved: SavedRoute
    var checkpoint: NavigationCheckpoint
    var elapsed: TimeInterval
    var updatedAt: Date
}
struct RideSummary: Codable, Identifiable {
    var id = UUID()
    var date = Date()
    var miles: Double
    var seconds: Double
    var completed: Bool
}
enum LocalFiles {
    static func url(_ name: String) throws -> URL {
        let directory = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                    appropriateFor: nil, create: true).appendingPathComponent("PedalLoop")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var excluded = directory
        var values = URLResourceValues(); values.isExcludedFromBackup = true
        try excluded.setResourceValues(values)
        return directory.appendingPathComponent(name)
    }
    static func read<T: Decodable>(_ name: String, as type: T.Type) -> T? {
        guard let url = try? url(name), let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }
    static func write<T: Encodable>(_ value: T, to name: String) throws {
        try JSONEncoder().encode(value).write(to: url(name), options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
    static func remove(_ name: String) throws {
        let file = try url(name)
        if FileManager.default.fileExists(atPath: file.path) { try FileManager.default.removeItem(at: file) }
    }
}
