"""
Test script for the Executor-based crafting system.

This demonstrates how to use the Executor parallel path for recursive crafting
without breaking the existing Action Agent flow.

Usage:
    # Test with executor mode
    python test_executor.py --mode executor

    # Test with traditional action agent mode
    python test_executor.py --mode action
"""

import argparse
from voyager import Voyager
import time

def test_executor_mode(voyager):
    """
    Test crafting with Executor mode.

    This uses direct primitive execution and recursive dependency resolution.
    """
    print("\n" + "="*70)
    print("TESTING EXECUTOR MODE")
    print("="*70 + "\n")
    
    voyager.env.reset()


    # Test 1: Craft planks (requires gathering logs)
    # print("\n--- Test 1: Craft Planks ---")
    # info = voyager.executor_craft("oak_planks")
    # print(f"Result: {info}")

    # # Test 2: Craft sticks (requires planks, which require logs)
    # print("\n--- Test 2: Craft Sticks ---")
    # info = voyager.executor_craft("sticks")
    # print(f"Result: {info}")

    # Test 3: Craft crafting table (requires planks)
    print("\n--- Test 1 ---")
    info = voyager.executor_craft("crafting table")
    print(f"Result: {info}")

    print("\n" + "="*70)
    print("EXECUTOR MODE TESTS COMPLETE")
    print("="*70 + "\n")


def test_action_mode(voyager):
    """
    Test crafting with traditional Action Agent mode.

    This uses LLM-based code generation.
    """
    print("\n" + "="*70)
    print("TESTING ACTION AGENT MODE")
    print("="*70 + "\n")

    # Run a few crafting tasks with the action agent
    voyager.learn(reset_env=True, use_executor=False)


def main():
    parser = argparse.ArgumentParser(description="Test Executor vs Action Agent modes")
    parser.add_argument(
        "--mode",
        choices=["executor", "action", "both"],
        default="executor",
        help="Which mode to test (default: executor)"
    )
    parser.add_argument(
        "--mc-port",
        type=int,
        default=25565,
        help="Minecraft server port"
    )

    args = parser.parse_args()

    # Get API key from environment if not provided
    import os
    with open(r"C:\Users\Alex\OneDrive - Naval Postgraduate School\Desktop\openAIKey.txt", "r") as f:
        api_key = f.read().strip()

    #api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Please provide OpenAI API key via --openai-api-key or OPENAI_API_KEY env var")
        return

    # Initialize Voyager
    print("Initializing Voyager...")
    voyager = Voyager(
        mc_host="10.0.132.101",
        mc_port=args.mc_port,
        openai_api_key=api_key,
        ckpt_dir="ckpt_executor_test",
        resume=False,
    )
    
    try:
        if args.mode == "executor":
            test_executor_mode(voyager)
        elif args.mode == "action":
            test_action_mode(voyager)
        elif args.mode == "both":
            test_executor_mode(voyager)
            test_action_mode(voyager)
    finally:
        voyager.close()
        print("\nVoyager closed.")


if __name__ == "__main__":
    main()
