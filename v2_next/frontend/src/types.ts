export interface FactoryData {
    // System
    Time: string;
    Status: string;
    
    // KPIs
    Speed: number | null;
    Press: number | null;
    Count: number | null;
    EndPos: number | null;
    Billet_Length: number | null;
    Die_ID?: string | null;
    Billet_Cycle_ID?: string | null;
    
    // Temperatures
    Spot: number | null;
    Temp_F: number | null;
    Temp_B: number | null;
    Billet_Temp: number | null;
    
    // Molds
    Mold1: number | null;
    Mold2: number | null;
    Mold3: number | null;
    Mold4: number | null;
    Mold5: number | null;
    Mold6: number | null;
    
    // Environment
    At_Temp: number | null;
    At_Pre: number | null;

    // Computed status (backend-derived)
    Computed?: ComputedStatus;
}

export interface ThresholdHits {
    speed: boolean;
    press: boolean;
    spot: boolean;
    temp_f: boolean;
    temp_b: boolean;
    billet: boolean;
    billet_temp: boolean;
    at_temp: boolean;
    at_pre: boolean;
    count: boolean;
    endpos: boolean;
}

export interface ComputedStatus {
    speed_level?: string;
    press_level?: string;
    spot_level?: string;
    spot_warning?: boolean;
    env_temp_level?: string;
    env_pre_level?: string;
    mold_levels?: Record<string, string>;
    jam_level?: string;
    thresholds?: ThresholdHits;
}

export interface SpotConfig {
    image_url: string;
    refresh_interval: number;
    crosshair_x: number;
    crosshair_y: number;
    crosshair_color: string;
    crosshair_thickness: number;
    crosshair_size: number;
    crosshair_gap: number;
    widget_width: number;
    widget_height: number;
    focus_step: number;
    focus_enabled: boolean;
}
