import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UploadScreen from "./UploadScreen";

function makeFile(name: string, type: string) {
  return new File(["contract content"], name, { type });
}

describe("UploadScreen", () => {
  it("accepts a valid PDF and calls onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<UploadScreen onFileSelected={onFileSelected} errorMessage={null} />);

    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = makeFile("contract.pdf", "application/pdf");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledTimes(1);
    expect(onFileSelected.mock.calls[0][0].name).toBe("contract.pdf");
  });

  it("rejects an unsupported file type and shows a local error, without calling onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<UploadScreen onFileSelected={onFileSelected} errorMessage={null} />);

    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = makeFile("not_a_contract.txt", "text/plain");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/Unsupported file type/)).toBeInTheDocument();
  });

  it("shows an error message passed down from a failed analysis attempt", () => {
    render(
      <UploadScreen
        onFileSelected={vi.fn()}
        errorMessage="Could not parse the uploaded file - it may be corrupted or not a valid PDF file."
      />
    );
    expect(screen.getByText(/Could not parse the uploaded file/)).toBeInTheDocument();
  });

  it("accepts a DOCX file too", () => {
    const onFileSelected = vi.fn();
    render(<UploadScreen onFileSelected={onFileSelected} errorMessage={null} />);

    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = makeFile(
      "contract.docx",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    );
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledTimes(1);
  });
});
