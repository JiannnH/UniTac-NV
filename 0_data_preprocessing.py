import csv
import numpy as np
import ast
import os
from datetime import datetime

class SensorDataProcessor:
    def __init__(self, file_path, sensor_type):
        """
        Initialize the processor.
        
        :param file_path: Path to the input CSV file.
        :param sensor_type: Type of sensor, either 'papillarray' or 'xela'.
        """
        self.file_path = file_path
        self.sensor_type = sensor_type.lower()
        if self.sensor_type not in ['papillarray', 'xela']:
            raise ValueError("sensor_type must be either 'papillarray' or 'xela'")
        self.data = None

    def load_data(self):
        """Loads data from the CSV file and parses it into structured arrays."""
        times, seqs = [], []
        sensor_matrices_force, sensor_matrices_displacement = [], []
        ft_values, end_effector_poses = [], []

        with open(self.file_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header
            for row in reader:
                times.append(row[0])
                seqs.append(int(row[1]))
                sensor_matrices_force.append(np.array(ast.literal_eval(row[2])))
                sensor_matrices_displacement.append(np.array(ast.literal_eval(row[3])))
                ft_values.append(np.array(ast.literal_eval(row[4])))
                end_effector_poses.append(np.array(ast.literal_eval(row[5])))

        self.data = {
            "times": times,
            "seqs": seqs,
            "sensor_matrices_force": sensor_matrices_force,
            "sensor_matrices_displacement": sensor_matrices_displacement,
            "ft_values": ft_values,
            "end_effector_poses": end_effector_poses,
        }
        for key in self.data.keys():
            self.data[key] = self.data[key][10:]

    def transform_data(self):
        """Applies transformations to force/torque values and flips matrices."""
        theta = np.pi / 4  # 45 degrees
        for i in range(len(self.data["ft_values"])):
            x, y, xm, ym = self.data["ft_values"][i][0], self.data["ft_values"][i][1], self.data["ft_values"][i][3], self.data["ft_values"][i][4]
            self.data["ft_values"][i][0] = x * np.cos(theta) - y * np.sin(theta)
            self.data["ft_values"][i][1] = y * np.cos(theta) + x * np.sin(theta)
            self.data["ft_values"][i][3] = xm * np.cos(theta) - ym * np.sin(theta)
            self.data["ft_values"][i][4] = ym * np.cos(theta) + xm * np.sin(theta)

        # Matching the coordinate system 
        if self.sensor_type == 'papillarray':
            for i in range(len(self.data["sensor_matrices_force"])):
                self.data["sensor_matrices_force"][i][:, :, 0] = -self.data["sensor_matrices_force"][i][:, :, 0]
                self.data["sensor_matrices_force"][i][:, :, 1] = -self.data["sensor_matrices_force"][i][:, :, 1]
                self.data["sensor_matrices_displacement"][i][:, :, 0] = -self.data["sensor_matrices_displacement"][i][:, :, 0]
                self.data["sensor_matrices_displacement"][i][:, :, 1] = -self.data["sensor_matrices_displacement"][i][:, :, 1]
        elif self.sensor_type == 'xela':
            pass

    def standardize_data(self):
        """Standardizes the sensor matrices by subtracting the mean of the first N samples."""
        sensor_matrices_force = np.array(self.data["sensor_matrices_force"], dtype=np.float64)
        sensor_matrices_displacement = np.array(self.data["sensor_matrices_displacement"], dtype=np.float64)

        n_samples = 100

        mean_force = np.mean(sensor_matrices_force[:n_samples], axis=0)
        mean_displacement = np.mean(sensor_matrices_displacement[:n_samples], axis=0)

        self.data["sensor_matrices_force"] -= mean_force
        self.data["sensor_matrices_displacement"] -= mean_displacement

        del self.data["seqs"]

    def zero_time(self):
        """Zeroes the time values."""
        start_time = datetime.strptime(self.data["times"][0], '%Y-%m-%d %H:%M:%S.%f')
        self.data["times"] = [(datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f') - start_time).total_seconds() for time in self.data["times"]]

    def sellect_data(self, lower_threshold, upper_threshold):
        """Select data points where force exceeds a certain threshold."""
        selected = []
        for i in range(len(self.data["ft_values"])):
            if -upper_threshold < self.data["ft_values"][i][2] < -lower_threshold:
                selected.append(i)
        
        if not selected:
            self.data['selected'] = []
            return

        # Group selected indices into blocks
        selected_blocks = []
        block = [selected[0]]
        
        for i in range(1, len(selected)):
            if selected[i] - selected[i-1] != 1:
                selected_blocks.append(block)
                block = [selected[i]]
            else:
                block.append(selected[i])
        
        selected_blocks.append(block)

        # Select minimum index per block with enough length
        indecies = []
        
        # Minimum block length depends on sensor type
        min_block_length = 5 if self.sensor_type == 'papillarray' else 30

        for block in selected_blocks:
            if len(block) < min_block_length:
                continue
            
            min_idx = min(block, key=lambda idx: self.data['ft_values'][idx][2])
            indecies.append(min_idx)
        
        self.data['selected'] = indecies
        if self.sensor_type == 'xela':
             print(f"Selected {len(indecies)} data points.")

    def calculate_angles(self):
        """Calculate angles of the end-effector trajectory."""
        center = [-0.15, 0.625]
        angles = []
        
        if 'selected' in self.data:
            for idx in self.data['selected']:
                x, y = self.data['end_effector_poses'][idx][:2]
                angle_deg = np.arctan2(y - center[1], x - center[0]) * 180 / np.pi + 90
                angles.append(round(angle_deg))
        
        self.data['angle'] = angles

    def save_data(self, save_path):
        """Save processed data to a .npz file."""
        np.savez(save_path, **self.data)

    def save_to_csv(self, csv_path):
        """Save processed data to a CSV file with flattened sensor matrices."""
        
        # Create a copy of the data to avoid modifying the original
        processed_data = self.data.copy()
        
        # Flatten 3D matrices to 2D
        reshape_dim_1 = 9 if self.sensor_type == 'papillarray' else 24

        if 'sensor_matrices_force' in processed_data:
            force_matrices = np.array(processed_data['sensor_matrices_force'])
            # Ensure we can reshape correctly given the varying Xela/Papillarray dimensions
            try:
                processed_data['sensor_matrices_force'] = force_matrices.reshape(
                    force_matrices.shape[0], reshape_dim_1, 3)
            except ValueError as e:
                print(f"Error reshaping force matrices for {self.sensor_type}: {e}")
        
        if 'sensor_matrices_displacement' in processed_data:
            displacement_matrices = np.array(processed_data['sensor_matrices_displacement'])
            try:
                processed_data['sensor_matrices_displacement'] = displacement_matrices.reshape(
                    displacement_matrices.shape[0], reshape_dim_1, 3)
            except ValueError as e:
                print(f"Error reshaping displacement matrices for {self.sensor_type}: {e}")
        
        # Prepare headers based on keys in data
        headers = list(processed_data.keys())
        
        # Get the maximum length of all arrays
        max_length = max(len(v) for v in processed_data.values())
        
        with open(csv_path, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for i in range(max_length):
                row_data = []
                for key in headers:
                    value = processed_data[key][i] if i < len(processed_data[key]) else None
                    
                    if isinstance(value, (np.ndarray, list)):
                        row_data.append(str(value.tolist() if isinstance(value, np.ndarray) else value))
                    else:
                        row_data.append(value)
                
                writer.writerow(row_data)

def process_all_files_and_save_csv(source_csv_path, sensor_type):
    print(f"--- Processing {sensor_type} data from {source_csv_path} ---")
    
    with open(source_csv_path, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Print the header
        print("CSV Header:", reader.fieldnames)
        
        for row in reader:
            original_path = row['Original Path']
            target_path_npz = row['Target Path']
            if os.path.exists(target_path_npz):
                print(f"Skipping: {original_path} -> {target_path_npz}")
                continue

            else:
                print(f"Processing: {original_path} -> {target_path_npz}")
                
                processor = SensorDataProcessor(original_path, sensor_type)
                
                processor.load_data()
                processor.transform_data()
                processor.standardize_data()
                processor.zero_time()
                processor.sellect_data(lower_threshold=5, upper_threshold=20)
                processor.calculate_angles()
                
                # Save .npz file
                target_dir_npz = os.path.dirname(target_path_npz)
                
                if not os.path.exists(target_dir_npz):
                    os.makedirs(target_dir_npz)
                
                processor.save_data(target_path_npz)
            
            # Save CSV file alongside .npz file
            target_csv_path = target_path_npz.replace('.npz', '.csv')
            processor.save_to_csv(target_csv_path)

if __name__ == "__main__":
    # Define paths
    papillarray_csv_index = 'Data_tracking/Data_preprocessing_papil.csv'
    xela_csv_index = 'Data_tracking/Data_preprocessing_xela.csv'

    # Papillarray
    if os.path.exists(papillarray_csv_index):
        process_all_files_and_save_csv(papillarray_csv_index, 'papillarray')
    else:
        print(f"Warning: {papillarray_csv_index} not found.")

    # Xela
    if os.path.exists(xela_csv_index):
        process_all_files_and_save_csv(xela_csv_index, 'xela')
    else:
        print(f"Warning: {xela_csv_index} not found.")