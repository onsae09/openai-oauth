import { Buffer } from "node:buffer"
import { describe, expect, test } from "vitest"
import { toModelMessages } from "../src/chat-messages.js"
import type { ChatMessage } from "../src/types.js"

describe("toModelMessages", () => {
	test("passes http image_url parts as URL image parts", () => {
		const messages: ChatMessage[] = [
			{
				role: "user",
				content: [
					{ type: "text", text: "review this" },
					{
						type: "image_url",
						image_url: { url: "https://example.com/screenshot.png" },
					},
				],
			},
		]

		const [message] = toModelMessages(messages)

		expect(message).toMatchObject({ role: "user" })
		expect(Array.isArray(message?.content)).toBe(true)
		const imagePart = Array.isArray(message?.content)
			? message.content[1]
			: undefined
		expect(imagePart).toMatchObject({ type: "image" })
		expect(imagePart?.type === "image" && imagePart.image).toBeInstanceOf(URL)
	})

	test("passes base64 data image_url parts as in-memory image bytes", () => {
		const base64Image = Buffer.from("png-bytes").toString("base64")
		const messages: ChatMessage[] = [
			{
				role: "user",
				content: [
					{ type: "text", text: "review this" },
					{
						type: "image_url",
						image_url: { url: `data:image/png;base64,${base64Image}` },
					},
				],
			},
		]

		const [message] = toModelMessages(messages)

		expect(message).toMatchObject({ role: "user" })
		expect(Array.isArray(message?.content)).toBe(true)
		const imagePart = Array.isArray(message?.content)
			? message.content[1]
			: undefined
		expect(imagePart).toMatchObject({
			type: "image",
			mediaType: "image/png",
		})
		expect(imagePart?.type === "image" && imagePart.image).toBeInstanceOf(
			Uint8Array,
		)
		expect(
			Buffer.from(
				imagePart?.type === "image" && imagePart.image instanceof Uint8Array
					? imagePart.image
					: [],
			).toString("utf-8"),
		).toBe("png-bytes")
	})

	test("handles image data URLs with extra parameters before base64", () => {
		const messages: ChatMessage[] = [
			{
				role: "user",
				content: [
					{
						type: "image_url",
						image_url: {
							url: "data:image/png;name=avatar.png;charset=utf-8;base64,iVBORw0KG",
						},
					},
				],
			},
		]

		const [message] = toModelMessages(messages)
		const imagePart = Array.isArray(message?.content)
			? message.content[0]
			: undefined

		expect(imagePart).toMatchObject({
			type: "image",
			mediaType: "image/png",
		})
		expect(imagePart?.type === "image" && imagePart.image).toBeInstanceOf(
			Uint8Array,
		)
	})

	test("passes non-image data URLs through as URL image parts", () => {
		const messages: ChatMessage[] = [
			{
				role: "user",
				content: [
					{
						type: "image_url",
						image_url: { url: "data:application/pdf;base64,AAAA" },
					},
				],
			},
		]

		const [message] = toModelMessages(messages)
		const imagePart = Array.isArray(message?.content)
			? message.content[0]
			: undefined

		expect(imagePart).toMatchObject({ type: "image" })
		expect(imagePart?.type === "image" && imagePart.image).toBeInstanceOf(URL)
	})
})
