import { createHash, timingSafeEqual } from "node:crypto"
import { readFile } from "node:fs/promises"
import { isRecord } from "./shared.js"

export const DEFAULT_API_KEYS_FILE = "api_key.json"

type StoredApiKey = {
	hash: string
	revoked_at?: string
}

type ApiKeyStore = {
	keys: StoredApiKey[]
}

export type ApiKeyAuthResult =
	| {
			ok: true
	  }
	| {
			ok: false
			message: string
	  }

const hashApiKey = (apiKey: string): string =>
	`sha256:${createHash("sha256").update(apiKey).digest("hex")}`

const isStoredApiKey = (value: unknown): value is StoredApiKey =>
	isRecord(value) &&
	typeof value.hash === "string" &&
	(value.revoked_at === undefined || typeof value.revoked_at === "string")

const parseApiKeyStore = (text: string): ApiKeyStore => {
	const value = JSON.parse(text) as unknown
	if (!isRecord(value) || !Array.isArray(value.keys)) {
		throw new Error("API key file must contain a `keys` array.")
	}

	return {
		keys: value.keys.filter(isStoredApiKey),
	}
}

const safeEqual = (left: string, right: string): boolean => {
	const leftBuffer = Buffer.from(left)
	const rightBuffer = Buffer.from(right)
	return (
		leftBuffer.byteLength === rightBuffer.byteLength &&
		timingSafeEqual(leftBuffer, rightBuffer)
	)
}

const extractApiKey = (request: Request): string | undefined => {
	const bearer = request.headers.get("authorization")?.trim()
	if (bearer?.toLowerCase().startsWith("bearer ")) {
		const token = bearer.slice("bearer ".length).trim()
		return token.length > 0 ? token : undefined
	}

	const headerKey = request.headers.get("x-api-key")?.trim()
	return headerKey && headerKey.length > 0 ? headerKey : undefined
}

export const resolveApiKeysFilePath = (filePath?: string): string =>
	filePath ?? DEFAULT_API_KEYS_FILE

export const authenticateApiKey = async (
	request: Request,
	filePath?: string,
): Promise<ApiKeyAuthResult> => {
	const apiKey = extractApiKey(request)
	if (!apiKey) {
		return {
			ok: false,
			message: "Missing API key. Send `Authorization: Bearer <api-key>`.",
		}
	}

	let store: ApiKeyStore
	try {
		store = parseApiKeyStore(
			await readFile(resolveApiKeysFilePath(filePath), "utf-8"),
		)
	} catch (error) {
		const detail = error instanceof Error ? error.message : String(error)
		return {
			ok: false,
			message: `No usable API keys configured. Create one with \`python3 scripts/api_keys.py\`. (${detail})`,
		}
	}

	const activeKeys = store.keys.filter((key) => key.revoked_at === undefined)
	if (activeKeys.length === 0) {
		return {
			ok: false,
			message:
				"No active API keys configured. Create one with `python3 scripts/api_keys.py`.",
		}
	}

	const hashedKey = hashApiKey(apiKey)
	const matches = activeKeys.some((key) => safeEqual(key.hash, hashedKey))

	return matches
		? { ok: true }
		: {
				ok: false,
				message: "Invalid API key.",
			}
}
