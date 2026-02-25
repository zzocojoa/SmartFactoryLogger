import os
import re

src_dir = r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\frontend\src"

rules = [
    ("domains/MESSync/components/mes", "components/mes"),
    ("domains/FacilityData/timeseries", "timeseries"),
    ("domains/FacilityData/components/widgets", "components/widgets"),
    ("domains/FacilityData/components/UPlotChart", "components/UPlotChart"),
    ("domains/FacilityData/api/metricService", "api/metricService"),
    ("domains/FacilityData/api/spotService", "api/spotService"),
    ("domains/FacilityData/hooks/useMetricsViewModel", "hooks/useMetricsViewModel"),
    ("domains/FacilityData/hooks/useSpotViewModel", "hooks/useSpotViewModel"),
    ("domains/Configuration/components/settings", "components/settings"),
    ("domains/Configuration/api/configService", "api/configService"),
    ("domains/Configuration/api/layoutService", "api/layoutService"),
    ("domains/Configuration/hooks/useConfigViewModel", "hooks/useConfigViewModel"),
    ("domains/Configuration/hooks/useLayoutViewModel", "hooks/useLayoutViewModel"),
    ("domains/Configuration/hooks/useViewportScale", "hooks/useViewportScale"),
    ("domains/Configuration/context/LayoutEditContext", "context/LayoutEditContext"),
    ("domains/Configuration/hooks/useLayoutEditContext", "hooks/useLayoutEditContext"),
    ("domains/Observability/api/systemService", "api/systemService"),
    ("domains/Observability/hooks/useSystemViewModel", "hooks/useSystemViewModel"),
    ("shared/components/common", "components/common"),
    ("shared/components/CustomDialog", "components/CustomDialog"),
    ("shared/api/client", "api/client"),
    ("shared/api/transport", "api/transport"),
    ("shared/hooks/useThemeContext", "hooks/useThemeContext"),
    ("shared/hooks/useGlobalModalContext", "hooks/useGlobalModalContext"),
    ("shared/context/ThemeContext", "context/ThemeContext"),
    ("shared/context/GlobalModalContext", "context/GlobalModalContext"),
    ("shared/utils", "utils"),
    ("shared/types", "types"),
    ("shared/constants", "constants"),
    ("shared/types.ts", "types.ts"),
]

def get_old_rel_path(new_rel_path):
    new_norm = new_rel_path.replace('\\', '/')
    for new_prefix, old_prefix in rules:
        if new_norm == new_prefix or new_norm.startswith(new_prefix + '/'):
            return new_norm.replace(new_prefix, old_prefix, 1)
    return new_norm

old_to_new = {}
for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith('.ts') or f.endswith('.tsx') or f.endswith('.css'):
            new_abs = os.path.join(root, f)
            new_rel = os.path.relpath(new_abs, src_dir).replace('\\', '/')
            old_rel = get_old_rel_path(new_rel)
            
            old_to_new[old_rel] = new_rel
            
            # also root extensions mapping
            base_old = os.path.splitext(old_rel)[0]
            base_new = os.path.splitext(new_rel)[0]
            old_to_new[base_old] = base_new
            
            if f == 'index.ts' or f == 'index.tsx':
                old_to_new[os.path.dirname(old_rel)] = os.path.dirname(new_rel)
                
# add custom fixes like just directories without index.ts?
for old_path, new_path in rules:
    old_to_new[old_path] = new_path

import_regex = re.compile(r'(import|export)(.*?from\s+)([\'"])(.*?)([\'"])', re.MULTILINE | re.DOTALL)
import_side_regex = re.compile(r'(import\s+)([\'"])(.*?)([\'"])', re.MULTILINE)

files_updated = 0

for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith('.ts') or f.endswith('.tsx'):
            new_abs = os.path.join(root, f)
            new_rel_path = os.path.relpath(new_abs, src_dir).replace('\\', '/')
            old_rel_path = get_old_rel_path(new_rel_path)
            old_dir = os.path.dirname(old_rel_path)
            new_dir = os.path.dirname(new_rel_path)
            
            with open(new_abs, 'r', encoding='utf-8') as f_obj:
                content = f_obj.read()
                
            original_content = content
            
            def replace_path(match):
                prefix_group = match.group(1)
                mid_group = match.group(2) if len(match.groups()) > 4 else ""
                quote1 = match.group(3) if len(match.groups()) > 4 else match.group(2)
                import_path = match.group(4) if len(match.groups()) > 4 else match.group(3)
                quote2 = match.group(5) if len(match.groups()) > 4 else match.group(4)
                
                if not import_path.startswith('.'):
                    return match.group(0) # Not a relative import
                
                # Resolve old import path
                # import_path is relative to old_dir
                resolved_old = os.path.normpath(os.path.join(old_dir, import_path)).replace('\\', '/')
                
                # If we mapped the exact old file or folder:
                if resolved_old in old_to_new:
                    resolved_new = old_to_new[resolved_old]
                    # Compute new relative path
                    new_import = os.path.relpath(resolved_new, new_dir).replace('\\', '/')
                    if not new_import.startswith('.'):
                        new_import = './' + new_import
                    
                    if len(match.groups()) > 4:
                        return f"{prefix_group}{mid_group}{quote1}{new_import}{quote2}"
                    else:
                        return f"{prefix_group}{quote1}{new_import}{quote2}"
                        
                # Might be we need to strip trailing slashes or similar
                return match.group(0)
                
            content = import_regex.sub(replace_path, content)
            content = import_side_regex.sub(replace_path, content)
            
            if content != original_content:
                with open(new_abs, 'w', encoding='utf-8') as f_obj:
                    f_obj.write(content)
                files_updated += 1
                
print(f"Updated imports in {files_updated} files.")
