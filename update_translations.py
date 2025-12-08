import json
import os
import glob

TRANSLATIONS_DIR = "/media/shaun/512Gb nVme/Projects/solis-modbus/custom_components/solis_modbus/translations"

def update_translations():
    files = glob.glob(os.path.join(TRANSLATIONS_DIR, "*.json"))
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding {file_path}")
                continue

        # 1. Fix duplicate/ensure existence in config.step.config.data
        if "config" in data and "step" in data["config"] and "config" in data["config"]["step"]:
             config_data = data["config"]["step"]["config"].setdefault("data", {})
             config_data["inverter_serial"] = "Inverter Serial" # Use English for all for now or keep existing
        
        # 2. Add to options.step.init.data
        if "options" in data and "step" in data["options"] and "init" in data["options"]["step"]:
             options_data = data["options"]["step"]["init"].setdefault("data", {})
             options_data["inverter_serial"] = "Inverter Serial"

        # 3. Add config.step.reconfigure
        if "config" in data and "step" in data["config"]:
            if "reconfigure" not in data["config"]["step"]:
                # specific logic for languages? 
                # For now, default to English structure but keep what we can. 
                # If specific language file, we might want to use English as placeholder.
                previous_config = data["config"]["step"]["config"]
                
                data["config"]["step"]["reconfigure"] = {
                    "title": "Reconfigure Inverter",
                    "description": "Update the configuration for your Solis inverter.",
                    "data": {
                         **previous_config.get("data", {}),
                         "inverter_serial": "Inverter Serial"
                    }
                }
            else:
                 # Ensure data key exists
                 reconfig_data = data["config"]["step"]["reconfigure"].setdefault("data", {})
                 reconfig_data["inverter_serial"] = "Inverter Serial"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Updated {file_path}")

if __name__ == "__main__":
    update_translations()
