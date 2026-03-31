class Dualentry < Formula
  desc "DualEntry accounting CLI"
  homepage "https://github.com/dualentry/dualentry-cli"
  version "0.1.0"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/dualentry/dualentry-cli/releases/download/v#{version}/dualentry-macos-arm64"
      sha256 "PLACEHOLDER"
    else
      url "https://github.com/dualentry/dualentry-cli/releases/download/v#{version}/dualentry-macos-x86_64"
      sha256 "PLACEHOLDER"
    end
  end

  on_linux do
    url "https://github.com/dualentry/dualentry-cli/releases/download/v#{version}/dualentry-linux-x86_64"
    sha256 "PLACEHOLDER"
  end

  def install
    binary = Dir["dualentry-*"].first || "dualentry"
    bin.install binary => "dualentry"
  end

  test do
    assert_match "dualentry-cli", shell_output("#{bin}/dualentry --version")
  end
end
