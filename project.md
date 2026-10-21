# Project: Lightweight Windows Auto-Lock Using Face Recognition

Act as a senior Windows desktop application engineer, computer vision engineer, and software architect. Your task is to design and eventually implement a lightweight Windows application that automatically locks my laptop when I walk away and ensures that it does not remain unlocked when someone else sits in front of it.

You have the freedom to choose and improve the architecture. Do not blindly follow the technologies or implementation ideas suggested below. Evaluate them critically, identify better alternatives when appropriate, and explain your decisions.

## 1. Core Objective

Build a Windows desktop application that:

1. Continuously or periodically monitors whether I am sitting in front of my laptop using its webcam.
2. Recognizes whether the detected person is me, rather than merely detecting that a face exists.
3. Automatically locks Windows when I leave the laptop.
4. Uses the actual Windows workstation-locking mechanism equivalent to Win + L.
5. Works on Windows laptops both with and without Windows Hello facial recognition.
6. Operates locally without requiring an internet connection or cloud service during normal use.
7. Runs quietly in the background with minimal CPU, RAM, battery, and storage consumption.

The primary purpose is automatic locking, not automatic unlocking.

## 2. Required Behavior

### A. Initial setup and face enrollment
- Provide a secure, simple way for me to enroll my face.
- Store only the minimum biometric data necessary.
- Process images locally and never upload camera frames or biometric data.
- Evaluate whether the enrolled facial data can be protected using Windows security facilities.
- Allow me to re-enroll or delete my facial data.
- Explain the security implications of storing facial embeddings locally.

### B. Continuous presence and identity monitoring
The application must distinguish between these states:

- My face is detected and recognized.
- A face is detected but belongs to someone else.
- No face is detected.
- Recognition is uncertain or unreliable.
- The camera is unavailable or has failed.

Do not treat an unknown face, an uncertain result, or a camera error as proof that I am present.

Evaluate suitable methods for:
- Face detection.
- Face recognition and similarity thresholds.
- Liveness detection or anti-spoofing, to reduce the risk of someone fooling the application with a photograph or screen.
- Detection of brief head turns, looking away, temporary occlusion, and changes in lighting.
- Reducing false positives and false negatives.

Do not claim that a basic webcam or an ordinary face-matching model provides reliable liveness detection unless the selected solution actually supports it.

### C. Automatic locking
- Lock the Windows workstation when my absence is confirmed for a configurable duration.
- Provide sensible default timing, such as 10–15 seconds, with configurable alternatives.
- Use the supported Windows API, such as LockWorkStation(), instead of simulating keyboard shortcuts.
- Ensure that open applications and work remain intact when Windows locks.
- Avoid repeated or unnecessary lock requests.
- Consider Windows session state, sleep, suspend, shutdown, and camera access failures.
- Never attempt to bypass Windows authentication or store Windows passwords.

### D. Background operation and user interface
The application should have:
- A system-tray icon.
- Start/stop monitoring controls.
- A clear current status.
- Configurable absence timeout and monitoring frequency.
- A camera preview or diagnostic screen only when explicitly requested.
- A way to enroll, replace, or delete my face profile.
- Automatic startup with Windows as an optional setting.
- Minimal notifications that do not become annoying.
- A safe way to pause monitoring when needed.

It should not require an open console window to function.

## 3. Compatibility Requirements

The application should target supported Windows 10/11 configurations, with exact OS requirements documented.

It must support:
- Standard USB or built-in webcams.
- Laptops without Windows Hello.
- Laptops with Windows Hello.
- Cameras that may be shared with other applications.
- Different webcam resolutions and frame rates.

Investigate Windows Hello, Windows biometric APIs, compatible infrared cameras, and any supported face-presence APIs. Do not assume a third-party desktop application can access Windows Hello's private biometric templates or continuously ask Windows Hello to verify a person's identity.

Use Windows Hello integration only if a supported, documented API genuinely enables the required behavior. Otherwise, provide an independent local face-recognition implementation that works without Windows Hello.

If any feature requires special hardware, make it optional and document the limitation.

## 4. Performance Requirements

This is a background utility, not a general-purpose AI application.

Optimize for:
- Low idle CPU usage.
- Low average RAM usage.
- Minimal battery drain.
- No mandatory GPU usage.
- No unnecessary background processes.
- No continuous full-resolution inference when it is unnecessary.
- Minimal disk usage.
- Fast startup and predictable shutdown.

Use intermittent camera sampling, reduced inference resolution, adaptive polling, and a compact model where appropriate.

Treat the following as initial targets to validate through benchmarks, not guaranteed results:
- Approximately 100–300 MB of RAM.
- Approximately 1–5% average CPU usage on a modern laptop during normal monitoring.
- No GPU requirement.
- A reasonably small standalone installation.

Measure actual resource consumption. If these targets are unrealistic for the selected model or hardware, explain why and propose optimizations rather than hiding the discrepancy.

Do not sacrifice identity accuracy or basic security merely to achieve lower resource usage.

## 5. Technology Selection

Initially consider:
- Python.
- OpenCV.
- A compact, locally running face-recognition model.
- A suitable local liveness-detection solution.
- PySide6 or another appropriate Windows desktop UI framework.
- Windows APIs for locking and startup integration.
- A suitable packaging tool for producing a standalone Windows executable.

However, these are suggestions, not fixed requirements.

Compare the practical alternatives, including a native Windows implementation using C#/.NET, if that would provide better performance, simpler distribution, stronger Windows integration, or lower maintenance overhead.

Choose the simplest architecture that satisfies the functional, security, performance, and distribution requirements.

Avoid unnecessary dependencies, paid APIs, cloud services, and complicated infrastructure. Prefer free and open-source components, while verifying their licenses and redistribution terms.

## 6. Security and Reliability

Explicitly analyze:
- False recognition of another person as me.
- Failure to recognize me under poor lighting.
- Spoofing with a photograph or displayed video.
- Biometric data protection.
- Malicious modification of local enrollment data.
- Camera permission and privacy.
- Camera failure or disconnection.
- Crashes and unexpected termination.
- Locking while I am still present.
- Failure to lock after I leave.
- Behavior when another person approaches after I leave.

The security priority is to avoid leaving my workstation unlocked because an unknown person is present.

Do not assume that a face being detected means it is me. Do not assume that face similarity alone proves a live person is in front of the camera.

Define conservative behavior for ambiguous cases. Explain any unavoidable trade-offs between convenience, security, battery consumption, and responsiveness.

## 7. Self-Correction and Plan Improvement

This requirement is especially important: do not merely produce the first plan that comes to mind.

Actively review and improve your own proposed solution.

Before implementation:

1. Inspect the available development environment, existing project files, Windows version, architecture, installed runtimes, and relevant hardware capabilities when accessible.
2. Identify missing information and distinguish verified facts from assumptions.
3. Research or verify important technical claims using authoritative documentation when research tools are available.
4. Compare at least two plausible architectural approaches.
5. Identify potential bottlenecks, unsupported APIs, dependency risks, licensing restrictions, security weaknesses, and compatibility problems.
6. Challenge your own initial design. Ask what could fail in real-world usage.
7. Consider edge cases such as multiple people in view, brief occlusion, lighting changes, a camera in use by another application, sleep/resume, and an unknown person replacing me.
8. Revise the plan based on these findings.
9. Perform a final critical review of the revised plan and explain which problems were fixed and which limitations remain.

Do not invent API capabilities, benchmark numbers, or compatibility guarantees. If something cannot be verified, explicitly label it as an assumption or an item to investigate.

If a requirement is technically impossible, insecure, or impractical as written, explain the issue and recommend a viable alternative instead of pretending it can be implemented exactly as requested.

You may propose improvements beyond my original requirements, but distinguish essential improvements from optional features.

## 8. Development and Testing Strategy

Create an incremental implementation plan with testable milestones.

Include:
- Environment and hardware assessment.
- Prototype for webcam access and face detection.
- Face enrollment and identity matching.
- Liveness/anti-spoofing evaluation.
- Presence-state and absence-timer logic.
- Windows workstation locking.
- Desktop interface and system-tray integration.
- Background execution and optional startup integration.
- Packaging and installation.
- Resource profiling.
- Security, reliability, and compatibility testing.

For each milestone, specify:
- The objective.
- Files or modules likely to be created.
- Dependencies.
- Acceptance criteria.
- Tests required.
- Risks and fallback approaches.

Include tests for both functional correctness and performance. Do not mark a milestone complete merely because the code compiles.

## 9. Working Rules

- Start by inspecting the environment and developing a plan.
- Do not immediately generate the entire application.
- Do not modify existing files or install dependencies before presenting the plan and obtaining my approval.
- Do not run destructive commands or change system security settings without explicit approval.
- Keep the architecture modular, maintainable, and easy to debug.
- Prefer small, verifiable implementation steps.
- Explain significant technical decisions in plain English.
- Preserve a clear distinction between working features, prototypes, and unverified assumptions.
- If an approach fails, diagnose the cause, revise the design, and explain the correction instead of repeatedly applying the same failed approach.

## 10. Required First Response

For now, ONLY inspect the environment to the extent safely possible and produce a detailed implementation plan. Do not implement the application yet.

Your response must contain:

1. Your understanding of the requirements.
2. Environment and hardware findings, with anything unavailable clearly identified.
3. A comparison of at least two viable technology architectures.
4. Your recommended architecture and justification.
5. The proposed face-recognition and liveness strategy.
6. The Windows locking and background-execution strategy.
7. A performance budget and a plan to measure actual resource consumption.
8. A proposed project structure.
9. An incremental development roadmap with acceptance criteria.
10. A risk assessment covering security, accuracy, compatibility, and maintenance.
11. A self-review of your initial design, the corrections you made, and the remaining limitations.
12. A list of decisions or permissions you need from me before implementation.

End with the final recommended plan and wait for my approval before making code changes or installing anything.