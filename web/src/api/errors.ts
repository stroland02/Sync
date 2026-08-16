/**
 * The ways a request can fail, as distinct types.
 *
 * One `Error` with a message string would make "the API is not running" and "that finding
 * is not open" the same thing on screen, and they are different answers: the first is a
 * broken deployment, the second is the graph telling the truth about a closed finding.
 */

/** The request never reached a server. `fetch` itself rejected — nothing answered. */
export class UnreachableApiError extends Error {
  readonly path: string

  constructor(path: string, options?: ErrorOptions) {
    super(`the request to ${path} never reached a server`, options)
    this.name = "UnreachableApiError"
    this.path = path
  }
}

/**
 * The API answered 404 with the identifier it could not find.
 *
 * Expected rather than exceptional: a finding that has been patched or abandoned is no
 * longer open, and the read surface says so by not holding it.
 */
export class NotFoundError extends Error {
  readonly identifier: string
  readonly path: string

  constructor(message: string, identifier: string, path: string) {
    super(message)
    this.name = "NotFoundError"
    this.identifier = identifier
    this.path = path
  }
}

/** A server answered, with a status the console cannot read as data. */
export class ApiStatusError extends Error {
  readonly status: number
  readonly path: string

  constructor(status: number, path: string) {
    super(`${path} answered HTTP ${status}`)
    this.name = "ApiStatusError"
    this.status = status
    this.path = path
  }
}

/** A 200 whose body is not the JSON the route documents. */
export class MalformedResponseError extends Error {
  readonly path: string

  constructor(path: string, options?: ErrorOptions) {
    super(`${path} answered with a body that is not JSON`, options)
    this.name = "MalformedResponseError"
    this.path = path
  }
}
