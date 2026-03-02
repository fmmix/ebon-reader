#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::{fs, sync::Mutex};

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

struct BackendSidecar(Mutex<Option<CommandChild>>);

fn terminate_backend_sidecar(app_handle: &tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<BackendSidecar>() {
        let mut guard = state.0.lock().expect("sidecar state lock poisoned");

        // Prevent orphaned sidecar processes when the desktop app exits.
        if let Some(mut child) = guard.take() {
            let _ = child.write(b"exit\n");
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendSidecar(Mutex::new(None)))
        .setup(|app| {
            let app_data_dir = app.path().app_data_dir()?;
            fs::create_dir_all(&app_data_dir)?;

            let db_path = app_data_dir.join("ebon_reader.db");
            let db_path_arg = db_path.to_string_lossy().into_owned();
            let debug_log_path = std::env::temp_dir().join("ebon_reader_sidecar.log");
            let debug_log_arg = debug_log_path.to_string_lossy().into_owned();
            let command = app.shell().sidecar("ebon_backend")?.args([
                "--debug-log",
                debug_log_arg.as_str(),
                "--db-path",
                db_path_arg.as_str(),
            ]);
            let (_receiver, child) = command.spawn()?;

            if let Some(state) = app.try_state::<BackendSidecar>() {
                let mut guard = state.0.lock().expect("sidecar state lock poisoned");
                *guard = Some(child);
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        match event {
            // Handle both paths to prevent orphan sidecar processes.
            RunEvent::ExitRequested { .. } | RunEvent::Exit => {
                terminate_backend_sidecar(app_handle)
            }
            _ => {}
        }
    });
}
