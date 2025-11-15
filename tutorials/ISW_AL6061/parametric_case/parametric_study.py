#!/usr/bin/env python3
"""
OpenFOAM Parametric Study Automation
Generates and submits multiple cases with varying parameters
"""
#make sure to change this path to the template folder
TEMPLATE_PATH = "/users/PNS0496/kanakbuet19/CFD/AL6061_trial/AL6061_trial"

import os
import shutil
import json
from pathlib import Path
import subprocess
import argparse
import pandas as pd



def load_csv_config(csv_file):
    """Load parameter sets from CSV file with default value handling"""
    print(f"📄 Loading CSV config: {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 CSV loaded with {len(df)} rows and {len(df.columns)} columns")
        print(f"🔍 CSV columns: {list(df.columns)}")
        
        parameter_sets = []
        
        # Default values for all parameters
        defaults = {
            'gravity_y': 9.81,  # Only Y component needed
            'laser_radius': '50e-6',
            'laser_e_num_density': '1.8e29',
            'laser_radius_flavour': '2.0',
            'powder_sim': 0,
            'phase_sigma': '0.91',
            'phase_dsigmadT': '-3.5e-4',
            'phase_beta_r': '0.2',
            'phase_p_amb': '101325.0',
            'phase_Tvap': '2792',
            'gas_nu': '1.48e-05',
            'gas_rho': '1',
            'gas_beta': '4.0e-5',
            'gas_poly_kappa': 0.0177,
            'gas_poly_cp': 520 ,
            'metal_elec_resistivity': '3.2e-7',
            'metal_emissivity': 0.15,
            'metal_T_ambient': 300,
            'metal_h_convection': 0.1,
            'mesh_width': 0.8e-3,
            'mesh_track_length': 2.0e-3,
            'mesh_patching_height': 0.5e-3,
            'mesh_size': 10e-6,
            'time_total_time': 2500e-6,
            'time_scan_speed': 0.7,
            'time_laser_power': 500,
            'time_initial_pos': 0.2e-3
        }
        
        for idx, row in df.iterrows():
            params = {}
            
            # Helper function to get value with default
            def get_value(col_name, default_val):
                if col_name in row and pd.notna(row[col_name]):
                    return row[col_name]
                else:
                    print(f"🔧 Using default for {col_name}: {default_val}")
                    return default_val
            
            # Gravity parameters (only Y component changes, X and Z stay 0)
            gravity_y = float(get_value('gravity_y', defaults['gravity_y']))
            params['gravity'] = (0, gravity_y, 0)  # Always (0, Y_value, 0)
            
            # Laser parameters
            laser_params = {}
            laser_params['radius'] = str(get_value('laser_radius', defaults['laser_radius']))
            laser_params['e_num_density'] = str(get_value('laser_e_num_density', defaults['laser_e_num_density']))
            laser_params['radius_flavour'] = str(get_value('laser_radius_flavour', defaults['laser_radius_flavour']))
            laser_params['powder_sim'] = bool(int(get_value('powder_sim', defaults['powder_sim'])))
            params['laser'] = laser_params
            
            # Phase parameters
            phase_params = {}
            phase_params['sigma'] = str(get_value('phase_sigma', defaults['phase_sigma']))
            phase_params['dsigmadT'] = str(get_value('phase_dsigmadT', defaults['phase_dsigmadT']))
            phase_params['p_amb'] = str(get_value('phase_p_amb', defaults['phase_p_amb']))
            phase_params['Tvap'] = str(get_value('phase_Tvap', defaults['phase_Tvap']))
            phase_params['beta_r'] = str(get_value('phase_beta_r', defaults['phase_beta_r'])) 
            params['phase'] = phase_params
            
            # Gas parameters
            gas_params = {}
            gas_params['nu'] = str(get_value('gas_nu', defaults['gas_nu']))
            gas_params['rho'] = str(get_value('gas_rho', defaults['gas_rho']))
            gas_params['beta'] = str(get_value('gas_beta', defaults['gas_beta']))
            gas_params['poly_kappa'] = [float(get_value('gas_poly_kappa', defaults['gas_poly_kappa']))]
            gas_params['poly_cp'] = [float(get_value('gas_poly_cp', defaults['gas_poly_cp']))]
            params['gas'] = gas_params
            
            # Metal parameters
         
            metal_params = {}
            metal_params['elec_resistivity'] = str(get_value('metal_elec_resistivity', defaults['metal_elec_resistivity']))
            metal_params['emissivity'] = float(get_value('emissivity', defaults['metal_emissivity']))
            # metal_params['T_ambient'] = float(get_value('T_ambient', defaults['metal_T_ambient']))
            metal_params['T_ambient'] = float(get_value('metal_T_ambient', defaults['metal_T_ambient']))

            metal_params['h_convection'] = float(get_value('h_convection', defaults['metal_h_convection']))
            params['metal'] = metal_params

   
            
            # Mesh parameters
            mesh_params = {}
            mesh_params['width'] = float(get_value('mesh_width', defaults['mesh_width']))
            mesh_params['track_length'] = float(get_value('mesh_track_length', defaults['mesh_track_length']))
            mesh_params['patching_height'] = float(get_value('mesh_patching_height', defaults['mesh_patching_height']))
            mesh_params['mesh_size'] = float(get_value('mesh_size', defaults['mesh_size']))
            params['mesh'] = mesh_params
            
            # Time parameters
            time_params = {}
            time_params['total_time'] = float(get_value('time_total_time', defaults['time_total_time']))
            time_params['scan_speed'] = float(get_value('time_scan_speed', defaults['time_scan_speed']))
            time_params['laser_power'] = float(get_value('time_laser_power', defaults['time_laser_power']))
            time_params['initial_pos'] = float(get_value('time_initial_pos', defaults['time_initial_pos']))
            params['time'] = time_params
            
            parameter_sets.append(params)
            print(f"✅ Case {idx + 1} parameters loaded (gravity_y: {gravity_y})")
        
        return parameter_sets
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return []



class OpenFOAMParametricStudy:
    def __init__(self, base_case_path, output_dir="parametric_cases"):
        self.base_case = Path(base_case_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_cases(self, parameter_sets):
        """Generate all parametric cases"""
        case_dirs = []
        
        for i, params in enumerate(parameter_sets):
            case_name = f"case_{i:03d}"
            case_dir = self.output_dir / case_name
            
            print(f"Generating {case_name}...")
            self._copy_base_case(case_dir)
            self._update_parameters(case_dir, params)
            case_dirs.append(case_dir)
            
        return case_dirs
    
    def _copy_base_case(self, case_dir):
        """Copy base case to new directory"""
        if case_dir.exists():
            shutil.rmtree(case_dir)
        shutil.copytree(self.base_case, case_dir)
    
    def _update_parameters(self, case_dir, params):
        """Update all parameters for a case"""
        # Update gravity
        self._update_g(case_dir, params.get('gravity', (0, 9.81, 0)))
        
        # Update laser properties
        laser_props = params.get('laser', {})
        self._update_laser_properties(case_dir, laser_props)
        
        # Update phase properties
        phase_props = params.get('phase', {})
        self._update_phase_properties(case_dir, phase_props)
        
        # Update gas properties
        gas_props = params.get('gas', {})
        self._update_gas_properties(case_dir, gas_props)
        
        # Update metal properties and get T_ambient
        metal_props = params.get('metal', {})
        T_ambient = self._update_metal_properties(case_dir, metal_props)

        # Update initial temperature field to match T_ambient
        self._update_initial_T(case_dir, T_ambient)

        
        # Update mesh
        mesh_params = params.get('mesh', {})
        self._update_mesh(case_dir, mesh_params)
        
        
        # Update simulation time and laser motion
        time_params = params.get('time', {})
        mesh_params = params.get('mesh', {})
        patching_height = mesh_params.get('patching_height', 0.5e-3)
        width = mesh_params.get('width', 0.8e-3)
        track_length = mesh_params.get('track_length', 2.0e-3)
        self._update_time_settings(case_dir, time_params, patching_height, width, track_length)

        # self._update_time_settings(case_dir, time_params, patching_height, width)

    
    def _update_g(self, case_dir, gravity):
        """Update gravity vector"""
        g_file = case_dir / "constant" / "g"
        content = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       uniformDimensionedVectorField;
    location    "constant";
    object      g;
}}

dimensions      [0 1 -2 0 0 0 0];
value           ({gravity[0]} {gravity[1]} {gravity[2]});
"""
        g_file.write_text(content)
    
    def _update_laser_properties(self, case_dir, props):
        """Update laser properties"""
        laser_file = case_dir / "constant" / "LaserProperties"
        
        # Read existing file
        content = laser_file.read_text()
        
        # Update parameters
        updates = {
            'laserRadius': props.get('radius', '50e-6'),
            'e_num_density': props.get('e_num_density', '1.8e29'),
            'Radius_Flavour': props.get('radius_flavour', '3.0'),
            'PowderSim': str(props.get('powder_sim', False)).lower()
        }
        
        for key, value in updates.items():
            content = self._replace_parameter(content, key, value)
        
        laser_file.write_text(content)
    
    def _update_phase_properties(self, case_dir, props):
        """Update phase properties"""
        phase_file = case_dir / "constant" / "phaseProperties"
        content = phase_file.read_text()
        
        updates = {
            'sigma': props.get('sigma', '0.21'),
            'dsigmadT': props.get('dsigmadT', '-3.5e-4'),
            'p0': props.get('p_amb', '101325.0'),
         
            'Tvap': props.get('Tvap', '2792'),
          
            'beta_r': props.get('beta_r', '0.2') 
            
        }
        
        for key, value in updates.items():
            content = self._replace_parameter(content, key, value)
        
        phase_file.write_text(content)
    
    def _update_gas_properties(self, case_dir, props):
        """Update gas properties"""
        gas_file = case_dir / "constant" / "physicalProperties.gas"
        content = gas_file.read_text()
        
        updates = {
            'nu': props.get('nu', '1.48e-05'),
            'rho': props.get('rho', '1'),
            'beta': props.get('beta', '4.0e-5')
        }
        
        for key, value in updates.items():
            content = self._replace_parameter(content, key, value)
        
        # Update polynomial coefficients
        if 'poly_kappa' in props:
            kappa = props['poly_kappa']
            content = self._replace_parameter(content, 'poly_kappa', f"({kappa[0]} 0 0 0 0 0 0 0)")
        
        if 'poly_cp' in props:
            cp = props['poly_cp']
            content = self._replace_parameter(content, 'poly_cp', f"({cp[0]} 0.0 0 0 0 0 0 0)")
        
        gas_file.write_text(content)
    


    def _update_metal_properties(self, case_dir, props):
        metal_file = case_dir / "constant" / "physicalProperties.metal"
        content = metal_file.read_text()

        if 'elec_resistivity' in props:
            content = self._replace_parameter(content, 'elec_resistivity', props['elec_resistivity'])
        if 'emissivity' in props:
            content = self._replace_parameter(content, 'emissivity', props['emissivity'])
        if 'T_ambient' in props:
            content = self._replace_parameter(content, 'T_ambient', props['T_ambient'])
        if 'h_convection' in props:
            content = self._replace_parameter(content, 'h_convection', props['h_convection'])

        metal_file.write_text(content)

        # Return ambient temperature for updating initial T field
        return float(props.get('T_ambient', 300.0))

    
    def _update_initial_T(self, case_dir, T_ambient):
        """Set initial temperature field to T_ambient"""
        T_file = case_dir / "initial" / "T"
        if not T_file.exists():
            print(f"⚠️ T file not found: {T_file}")
            return

        content = T_file.read_text()

        import re
        # Replace internalField uniform value
        pattern = r'(internalField\s+uniform\s+)([\d.eE+-]+)'
        replacement = rf'\g<1>{T_ambient}'
        
        if re.search(pattern, content):
            old_val = re.search(pattern, content).group(2)
            print(f"🔄 Setting initial T: {old_val} → {T_ambient}")
            content = re.sub(pattern, replacement, content)
        else:
            print(f"⚠️ Could not find internalField in {T_file}, skipping update")

        T_file.write_text(content)
    

    
    def _update_mesh(self, case_dir, mesh_params):
        """Update mesh parameters"""
        mesh_file = case_dir / "system" / "blockMeshDict"
        content = mesh_file.read_text()
        
        # Get mesh parameters
        width = mesh_params.get('width', 0.6e-3)
        track_length = mesh_params.get('track_length', 2.0e-3)
        patching_height = mesh_params.get('patching_height', 0.3e-3)
        
        gas_phase_height = 120e-6 
        
        mesh_height = patching_height + gas_phase_height
        mesh_size = mesh_params.get('mesh_size', 10e-6)
        
        # Calculate cell numbers
        nx = int(width / mesh_size)
        ny = int(track_length / mesh_size)
        nz = int(mesh_height / mesh_size)
        
        # Update vertices
        vertices = f"""vertices
(
    (0          0          0)         // 0
    ({width}    0          0)         // 1
    ({width}    {track_length}    0)         // 2
    (0          {track_length}    0)         // 3
    (0          0          {mesh_height})   // 4
    ({width}    0          {mesh_height})   // 5
    ({width}    {track_length}    {mesh_height})   // 6
    (0          {track_length}    {mesh_height})   // 7
);"""
        
        # Update blocks
        blocks = f"""blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);"""
        
        # Replace in content
        content = self._replace_section(content, 'vertices', vertices)
        content = self._replace_section(content, 'blocks', blocks)
        
        mesh_file.write_text(content)

        # --- Also update bedPlateDict zmax to match patching_height ---
        bedplate_file = case_dir / "system" / "bedPlateDict"
        if bedplate_file.exists():
            bedplate_content = bedplate_file.read_text()

            import re
            pattern = r'(zmax\s+)([^;]+)(;)'
            replacement = rf'\g<1>{patching_height}\g<3>'

            if not re.search(pattern, bedplate_content):
                print(f"⚠️ zmax not found in {bedplate_file}, skipping update")
            else:
                old_val = re.search(pattern, bedplate_content).group(2).strip()
                print(f"🔄 Updating bedPlateDict zmax: {old_val} → {patching_height}")
                bedplate_content = re.sub(pattern, replacement, bedplate_content)
                bedplate_file.write_text(bedplate_content)

            pattern_ymax = r'(ymax\s+)([^;]+)(;)'
            replacement_y = rf'\g<1>{track_length}\g<3>'

            if not re.search(pattern_ymax, bedplate_content):
                print(f"⚠️ ymax not found in {bedplate_file}, skipping update")
            else:
                old_ymax = re.search(pattern_ymax, bedplate_content).group(2).strip()
                print(f"🔄 Updating bedPlateDict ymax: {old_ymax} → {track_length}")
                bedplate_content = re.sub(pattern_ymax, replacement_y, bedplate_content)
                bedplate_file.write_text(bedplate_content)
                
            pattern_xmax = r'(xmax\s+)([^;]+)(;)'
            replacement_x = rf'\g<1>{width}\g<3>'

            if not re.search(pattern_xmax, bedplate_content):
                print(f"⚠️ xmax not found in {bedplate_file}, skipping update")
            else:
                old_xmax = re.search(pattern_xmax, bedplate_content).group(2).strip()
                print(f"🔄 Updating bedPlateDict xmax: {old_xmax} → {width}")
                bedplate_content = re.sub(pattern_xmax, replacement_x, bedplate_content)
                bedplate_file.write_text(bedplate_content)


    
    # def _update_time_settings(self, case_dir, time_params, patching_height, width):
    def _update_time_settings(self, case_dir, time_params, patching_height, width, track_length):


        """Update time-related settings"""
        total_time = time_params.get('total_time', 2500e-6)
        scan_speed = time_params.get('scan_speed', 0.7)  # m/s
        laser_power = time_params.get('laser_power', 500)
        
        # Update controlDict
        control_file = case_dir / "system" / "controlDict"
        content = control_file.read_text()
        content = self._replace_parameter(content, 'endTime', f'{total_time}')
        control_file.write_text(content)
        
        # Calculate scan distance
        initial_pos = time_params.get('initial_pos', 0.12e-3)
        laser_distance = 1.5e-3 #hardcoded
        cooling_time = 500e-6
        laser_on_time =  laser_distance / scan_speed # matches your laser power ramp
        # total_distance = initial_pos + scan_speed * laser_on_time
        required_time = laser_on_time + + cooling_time
      
        if total_time < required_time  : raise ValueError (f"Increase simulation total time")
        print(f"Set the total_time to {required_time *1e6} µs")
        
        # if total_distance > track_length:
        #     raise ValueError(f"❌ scan_distance ({total_distance:.4e} m) exceeds track_length. Fix CSV input!")

        
        # Use patching_height for the 2nd coordinate
        # patching_height = mesh_params.get('patching_height', 0.5e-3)
        end_position = laser_distance + initial_pos

        pos_file = case_dir / "constant" / "timeVsLaserPosition"
        half_width = width / 2 
        move_time = laser_distance / scan_speed 


        pos_content = f"""(
            (0            ({half_width} {patching_height} {initial_pos}))
            ({move_time}  ({half_width} {patching_height} {end_position}))
            ({total_time} ({half_width} {patching_height} {end_position}))
        )
        """

        pos_file.write_text(pos_content)

        
        # Update laser power
        power_file = case_dir / "constant" / "timeVsLaserPower"
        ramp_start = 1e-8
        # steady_start = 800e-6
        steady_end = move_time 
        power_off = move_time + 1e-6
        
        power_content = f"""


(
    (0              10)
    ({ramp_start}   {laser_power})
    ({steady_end}   {laser_power})
    ({power_off}    0)
    ({total_time}   0)
)
"""
        power_file.write_text(power_content)
    
    def _replace_parameter(self, content, param_name, value):
        """Replace parameter value in OpenFOAM file"""
        import re
        pattern = rf'({param_name}\s+)([^;]+)(;)'
        replacement = rf'\g<1>{value}\g<3>'
        
        # Debug: Check if parameter exists
        if not re.search(pattern, content):
            print(f"⚠️  Parameter '{param_name}' not found in file")
            return content
        
        # Debug: Show what's being replaced
        match = re.search(pattern, content)
        if match:
            old_value = match.group(2).strip()
            print(f"🔄 Replacing {param_name}: '{old_value}' → '{value}'")
        
        return re.sub(pattern, replacement, content)
    
    def _replace_section(self, content, section_name, new_section):
        import re
        # Match the section keyword, then everything until the closing ');'
        pattern = rf'{section_name}\s*\(.*?\);\s*'
        return re.sub(pattern, new_section, content, flags=re.DOTALL)


    
    def create_job_script(self, case_dir, job_name=None):
        """Create SLURM job script for a case"""
        if job_name is None:
            job_name = case_dir.name
        
        print(f"📝 Creating job script for case: {case_dir}")
        
        job_script = f"""#!/bin/bash

#SBATCH --job-name={job_name}
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --account=PNS0496
#SBATCH --output=output_%j.out
#SBATCH --error=output_%j.err

cd $SLURM_SUBMIT_DIR

# Clean MPI settings
module purge
unset OMPI_MCA_*
unset MPI_HOME

# Setup OpenMPI and OpenFOAM
export PATH="$HOME/openmpi-5.0.7-install/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/openmpi-5.0.7-install/lib${{LD_LIBRARY_PATH:+:}}$LD_LIBRARY_PATH"
export WM_PROJECT_DIR=$HOME/OpenFOAM-10
source "$WM_PROJECT_DIR/etc/bashrc"
export FOAM_SIGFPE=0

# Source tutorial run functions
. $WM_PROJECT_DIR/bin/tools/RunFunctions

echo "Job started at: $(date)"
echo "Case: {job_name}"



# Setup case
cp -r initial 0
runApplication blockMesh
runApplication setSolidFraction
runApplication transformPoints "rotate=((0 1 0) (0 0 1))"
decomposePar

# Start monitoring in background
dos2unix recon_test
./recon_test &
MONITOR_PID=$!

# Run simulation
mpirun -np $SLURM_NTASKS laserbeamFoam -parallel

# Final reconstruction
reconstructPar
foamToVTK -useTimeName

# Stop monitoring
kill $MONITOR_PID 2>/dev/null || true

echo "Job completed at: $(date)"
"""
        
        job_file = case_dir / "job.sh"
        print(f"📁 Job file path: {job_file}")
        
        try:
            job_file.write_text(job_script)
            job_file.chmod(0o755)
            print(f"✅ Job script written and made executable")
        except Exception as e:
            print(f"❌ Error creating job script: {e}")
        
        return job_file
    
    def submit_jobs(self, case_dirs, submit=False):
        """Create job scripts and optionally submit them"""
        job_files = []
        
        for case_dir in case_dirs:
            # Copy recon_test script
            recon_script = case_dir / "recon_test"
            base_recon = self.base_case / "recon_test"
            if base_recon.exists():
                shutil.copy2(base_recon, recon_script)
                recon_script.chmod(0o755)
            
            # Create job script
            job_file = self.create_job_script(case_dir)
            job_files.append(job_file)
            
            if submit:
                print(f"Submitting job for {case_dir.name}...")
                # subprocess.run(["sbatch", str(job_file)], cwd=case_dir)
                subprocess.run(["sbatch", job_file.name], cwd=case_dir)

        
        return job_files


def main():
    # Hardcoded base case path
    BASE_CASE_PATH = TEMPLATE_PATH 
    
    parser = argparse.ArgumentParser(description="Generate OpenFOAM parametric study")
    parser.add_argument("--config", help="JSON config file with parameter sets")
    parser.add_argument("--csv", help="CSV config file with parameter sets") 
    parser.add_argument("--output", default="cases", help="Output directory name")
    parser.add_argument("--submit", action="store_true", help="Submit jobs immediately")


    parser.add_argument("--create-examples", action="store_true", help="Create example CSV files")
    args = parser.parse_args()

    # Add this right after args parsing:
    if args.create_examples:
        create_example_csvs()
        return
        


    
    
    # Check if base case exists
    base_case = Path(BASE_CASE_PATH)
    if not base_case.exists():
        print(f"❌ Base case not found: {BASE_CASE_PATH}")
        print("Check the hardcoded path in the script!")
        return
    
    print(f"📁 Using base case: {BASE_CASE_PATH}")
    print(f"📁 Working directory: {Path.cwd()}")

    # Load parameter sets
    if args.csv and Path(args.csv).exists():
        parameter_sets = load_csv_config(args.csv)

    elif args.config and Path(args.config).exists():
        print(f"📄 Loading JSON config: {args.config}")
        try:
            with open(args.config) as f:
                config_data = json.load(f)
                if isinstance(config_data, list):
                    parameter_sets = config_data
                else:
                    parameter_sets = config_data.get('cases', [])
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            parameter_sets = [{"time": {"laser_power": 500}}]

    else:
        print("⚠️  No config file specified, using default parameter sweep")
        parameter_sets = [
            {"laser": {"radius": "40e-6"}, "time": {"total_time": 2000e-6, "scan_speed": 0.8, "laser_power": 400}, "mesh": {"mesh_size": 8e-6}},
            {"laser": {"radius": "50e-6"}, "time": {"total_time": 2500e-6, "scan_speed": 0.7, "laser_power": 500}, "mesh": {"mesh_size": 10e-6}},
            {"laser": {"radius": "60e-6"}, "time": {"total_time": 3000e-6, "scan_speed": 0.6, "laser_power": 600}, "mesh": {"mesh_size": 12e-6}}
        ]

    

    print(f"🔄 Generating {len(parameter_sets)} cases...")
    
    # Generate study
    study = OpenFOAMParametricStudy(BASE_CASE_PATH, args.output)
    case_dirs = study.generate_cases(parameter_sets)
    job_files = study.submit_jobs(case_dirs, args.submit)
    
    print(f"✅ Generated {len(case_dirs)} cases in {args.output}/")
    print(f"📂 Cases created:")
    for case_dir in case_dirs:
        print(f"   - {case_dir.name}")
    
    if args.submit:
        print("🚀 Jobs submitted to SLURM queue")
        print("Monitor with: squeue -u $USER")
    else:
        print("💡 Job scripts created. Submit manually with:")
        print(f"   cd {args.output}/case_XXX && sbatch job.sh")


def create_example_csvs():
    """Create example CSV files for testing"""
    
    # Full CSV with all parameters
    full_csv = """laser_radius,laser_e_num_density,laser_radius_flavour,powder_sim,phase_sigma,phase_dsigmadT,phase_p_amb,phase_Tvap,gas_nu,gas_rho,gas_beta,gas_poly_kappa,gas_poly_cp,metal_elec_resistivity,mesh_width,mesh_track_length,mesh_patching_height,mesh_size,time_total_time,time_scan_speed,time_laser_power
40e-6,1.5e29,2.5,0,0.20,-3.0e-4,95000,2800,1.40e-05,0.9,3.8e-5,0.025,1000,6.5e-7,0.5e-3,1.8e-3,0.4e-3,8e-6,2000e-6,0.8,400
60e-6,2.0e29,3.5,1,0.22,-4.0e-4,105000,2750,1.55e-05,1.1,4.2e-5,0.028,1015,7.5e-7,0.7e-3,2.2e-3,0.6e-3,12e-6,3000e-6,0.6,600"""
    
    with open('full_parameters.csv', 'w') as f:
        f.write(full_csv)
    
    # Partial CSV with only some parameters
    partial_csv = """laser_radius,time_laser_power,mesh_size
45e-6,450,9e-6
55e-6,550,11e-6"""
    
    with open('partial_parameters.csv', 'w') as f:
        f.write(partial_csv)
    
    print("📄 Created example CSV files:")
    print("   - full_parameters.csv (all columns)")
    print("   - partial_parameters.csv (partial columns)")


if __name__ == "__main__":
    main()
