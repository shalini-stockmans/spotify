# import os
# import json
# import shutil
# from datetime import datetime

# original_files_folder = "Z://Employees//Shalini Docs//Tests//original"
# json_files_folder = "Z://Employees//Shalini Docs//Tests//info"
# new_files_folder = "Z://Employees//Shalini Docs//Tests//new"

# os.makedirs(new_files_folder, exist_ok=True)

# for original_file in os.listdir(original_files_folder):
#     original_file_path = os.path.join(original_files_folder, original_file)

#     if not os.path.isfile(original_file_path):
#         continue

#     new_file_path = os.path.join(new_files_folder, original_file)
#     try:
#         shutil.copy2(original_file_path, new_file_path)
#         print(f"Copied {original_file} to {new_files_folder}")
#     except Exception as e:
#         print(f"Error copying {original_file}: {e}")
#         continue

#     json_file_name = f"{original_file}-info"
#     json_file_path = os.path.join(json_files_folder, json_file_name)

#     if not os.path.exists(json_file_path):
#         print(f"JSON file not found for: {original_file}")
#         continue

#     with open(json_file_path, "r") as json_file:
#         try:
#             json_data = json.load(json_file)
#         except json.JSONDecodeError:
#             print(f"Error reading JSON file: {json_file_name}")
#             continue

#     last_modified_str = json_data.get("last_modified_by_any_user")
#     if not last_modified_str:
#         print(f"No 'last_modified_by_any_user' field in JSON file: {json_file_name}")
#         continue

#     try:
#         last_modified_dt = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
#         last_modified_timestamp = last_modified_dt.timestamp()
#     except ValueError:
#         print(f"Invalid date format in JSON file: {json_file_name}")
#         continue

#     # Update the modified time of the copied file
#     try:
#         os.utime(new_file_path, (last_modified_timestamp, last_modified_timestamp))
#         print(f"Updated modified time for: {original_file}")
#     except Exception as e:
#         print(f"Error updating modified time for {original_file}: {e}")


# def update_file_modified_date(file_path, modified_date_str):
#     try:
#         modified_time = datetime.strptime(modified_date_str, "%Y-%m-%dT%H:%M:%S").timestamp()
#         os.utime(file_path, (modified_time, modified_time))
#         print(f"Updated modified date of '{file_path}' to '{modified_date_str}'")
#     except Exception as e:
#         print(f"Error updating file '{file_path}': {e}")

#     # file_location = "Z://Employees//Will Docs//0 SS Files Saved//orginal_files//Wood Book 4-at-2020-06-22T14_59_41.073Z-pinned.docx" 
#     # new_modified_date = "2020-06-2T14:59:41"  

#     # update_file_modified_date(file_location, new_modified_date)


import os
import json
import time
import re
import shutil

def update_image_modified_time(master_folder):
    for root, dirs, files in os.walk(master_folder):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg")):
                image_path = os.path.join(root, file)
                if "-edited" in file.lower():
                    # Handle files ending with "-edited"
                    original_file = file.replace("-edited", "")
                    json_path = os.path.join(root, f"{original_file}.json")
                elif re.search(r"\(\d\)\.jpg$", file, re.IGNORECASE):
                    # Handle files ending with (1) (2) or (3)
                    match = re.search(r"\(\d\)\.jpg$", file, re.IGNORECASE)
                    if match:
                        base_name = file[:file.rfind("(")].strip()  
                        suffix = file[file.rfind("("):].replace(".jpg", "")  
                        json_path = os.path.join(root, f"{base_name}.jpg{suffix}.json")
                    else:
                        continue
                else:
                    json_path = f"{image_path}.json"

                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r") as json_file:
                            data = json.load(json_file)
                        if "photoTakenTime" in data and "timestamp" in data["photoTakenTime"]:
                            timestamp = int(data["photoTakenTime"]["timestamp"])
                            os.utime(image_path, (timestamp, timestamp))
                            print(f"Updated modified time for {image_path} to {time.ctime(timestamp)}")
                        else:
                            print(f"photoTakenTime not found in JSON for {image_path}")
                    except Exception as e:
                        print(f"Error processing {json_path}: {e}")
                else:
                    print(f"No JSON file found for {image_path}")

# Replace with your master folder path
# master_folder_path = r"D://Dan's Pictures//Takeout//Google Photos"
# update_image_modified_time(master_folder_path)


# move all the info files to a json folder


def move_json_files(master_folder, info_folder):

    if not os.path.exists(info_folder):
        os.makedirs(info_folder)
        print(f"Created info folder: {info_folder}")

    for root, _, files in os.walk(master_folder):
        for file in files:
            if file.endswith('.json'):
                source_path = os.path.join(root, file)
                destination_path = os.path.join(info_folder, file)

                # Handle potential file name conflicts
                if os.path.exists(destination_path):
                    base, ext = os.path.splitext(file)
                    counter = 1
                    while os.path.exists(destination_path):
                        destination_path = os.path.join(info_folder, f"{base}_{counter}{ext}")
                        counter += 1

                shutil.move(source_path, destination_path)
                print(f"Moved: {source_path} -> {destination_path}")

    print("All .json files have been moved.")


# Example usage
master_folder = r"D://Dan's Pictures//Takeout//Google Photos"  # Replace with the path to your master folder
info_folder = r"D://Dan's Pictures//Takeout//Google Photos//00 JSON INFO FILES"  # Replace with the path to your info folder

# move_json_files(master_folder, info_folder)


