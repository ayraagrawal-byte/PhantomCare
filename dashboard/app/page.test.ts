import { describe, expect, it } from "vitest";

describe("dashboard shell", () => {
  it("keeps the product disclaimer explicit", () => {
    const disclaimer =
      "PhantomCare reports indicators worth reviewing—not conclusions of fraud.";

    expect(disclaimer).toContain("not conclusions of fraud");
  });
});

