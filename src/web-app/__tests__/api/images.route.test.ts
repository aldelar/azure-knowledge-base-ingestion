import { GET } from "../../app/api/images/[...path]/route";

const { downloadServingImage } = vi.hoisted(() => ({
  downloadServingImage: vi.fn(),
}));

vi.mock("../../lib/blob", () => ({
  downloadServingImage,
}));

describe("image proxy route", () => {
  beforeEach(() => {
    downloadServingImage.mockReset();
  });

  it("returns 400 when the requested image path is incomplete", async () => {
    const response = await GET(new Request("http://localhost/api/images/article-only"), {
      params: Promise.resolve({ path: ["article-only"] }),
    });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "invalid_path" });
    expect(downloadServingImage).not.toHaveBeenCalled();
  });

  it("returns 404 when the backing blob is missing", async () => {
    downloadServingImage.mockResolvedValue(null);

    const response = await GET(new Request("http://localhost/api/images/article/images/diagram.png"), {
      params: Promise.resolve({ path: ["article", "images", "diagram.png"] }),
    });

    expect(downloadServingImage).toHaveBeenCalledWith("article", "images/diagram.png");
    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "not_found" });
  });

  it("streams the downloaded blob with cache and content headers", async () => {
    downloadServingImage.mockResolvedValue({
      data: Buffer.from("png-bytes"),
      contentType: "image/png",
    });

    const response = await GET(new Request("http://localhost/api/images/article/images/diagram.png"), {
      params: Promise.resolve({ path: ["article", "images", "diagram.png"] }),
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("public, max-age=3600");
    expect(response.headers.get("Content-Type")).toBe("image/png");
    await expect(response.text()).resolves.toBe("png-bytes");
  });
});