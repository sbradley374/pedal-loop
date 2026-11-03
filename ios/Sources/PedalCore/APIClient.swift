import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum APIError: LocalizedError {
    case invalidURL, unauthorized, server(String), timedOut, invalidResponse
    public var errorDescription: String? {
        switch self {
        case .invalidURL: return "Enter the HTTPS server address, without a path, query, or password."
        case .unauthorized: return "Sign-in failed. Check the beta username and password in Server settings."
        case .server(let message): return message
        case .timedOut: return "The route search took too long. Try a shorter distance or another start."
        case .invalidResponse: return "The server returned an unreadable response. Check the server address."
        }
    }
}

/// All endpoints stay on one HTTPS origin. Redirects are refused so credentials cannot follow them.
public final class APIClient: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    private struct Message: Decodable { var error: String }
    public let baseURL: URL
    private let authorization: String?
    private var session: URLSession!
    public static func validatedURL(_ text: String) throws -> URL {
        guard let url = URL(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme == "https", let host = url.host, !host.isEmpty,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              url.path.isEmpty || url.path == "/" else { throw APIError.invalidURL }
        return url
    }
    public init(address: String, username: String, password: String) throws {
        baseURL = try Self.validatedURL(address)
        authorization = username.isEmpty && password.isEmpty ? nil : "Basic " + Data("\(username):\(password)".utf8).base64EncodedString()
        super.init()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 45
        configuration.urlCredentialStorage = nil
        configuration.httpCookieStorage = nil
        session = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }
    public func close() { session.invalidateAndCancel() }
    public func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                           newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
    private func request<T: Decodable>(_ path: String, method: String = "GET", body: Data? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = method; request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(authorization, forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        if response.statusCode == 401 { throw APIError.unauthorized }
        guard (200..<300).contains(response.statusCode) else {
            let message = (try? JSONDecoder().decode(Message.self, from: data).error) ?? "Server error (\(response.statusCode)). Try again shortly."
            throw APIError.server(message)
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError.invalidResponse }
    }
    public func info() async throws -> ServerInfo { try await request("api/info") }
    public func submit(_ preferences: SearchRequest) async throws -> RouteJob {
        try await request("api/route-jobs", method: "POST", body: JSONEncoder().encode(preferences))
    }
    public func job(_ id: String) async throws -> RouteJob { try await request("api/route-jobs/\(id)") }
    public func cancel(_ id: String) async throws { let _: RouteJob = try await request("api/route-jobs/\(id)", method: "DELETE") }
    public func result(_ id: String) async throws -> RouteResult { try await request("api/results/\(id)") }
}
