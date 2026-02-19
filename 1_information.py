import numpy as np
import os
import json

# Define the folder paths 
folders = {'Xela': 'UniTac-NV Dataset Processed/Xela', 'PapillArray': 'UniTac-NV Dataset Processed/PapillArray'}

dataset_info = {}

# Iterate through each folder and file
for folder_name, folder_path in folders.items():
    dataset_info[folder_name] = {}
    if os.path.exists(folder_path):  
        for file_name in os.listdir(folder_path):
            if file_name.endswith('.npz'):
                file_path = os.path.join(folder_path, file_name)
                data = np.load(file_path)
                
                # Extract information about the dataset
                file_info = {}
                for key in data:
                    array = data[key]
                    file_info[key] = {
                        'shape': array.shape,
                        'dtype': array.dtype.name,
                        'mean': float(array.mean()),
                        'min': float(array.min()),
                        'max': float(array.max())
                    }
                dataset_info[folder_name][file_name] = file_info
    else:
        print(f"Folder not found: {folder_path}")

# Save the dataset information 

with open('dataset_info.json', 'w') as json_file:
    json.dump(dataset_info, json_file, indent=4)

print("Dataset information has been saved to 'dataset_info.json'.")
