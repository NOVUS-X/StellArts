use stellar_cli as stellar;
use std::process::Command;

fn main() {
    println!("Building StellArts Smart Contracts...\n");

    // Build all contracts
    let status = Command::new("cargo")
        .args(&["build", "--release", "--target", "wasm32-unknown-unknown"])
        .status()
        .expect("Failed to build contracts");

    if status.success() {
        println!("\n✅ Contracts built successfully!");
        println!("\nBuilt contracts:");
        println!("  - escrow.wasm");
        println!("  - reputation.wasm");
        println!("\nLocation: target/wasm32-unknown-unknown/release/");
    } else {
        eprintln!("\n❌ Build failed!");
        std::process::exit(1);
    }
}
