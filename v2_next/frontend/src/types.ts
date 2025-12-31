export interface FactoryData {
    // System
    Time: string;
    Status: string;
    
    // KPIs
    Speed: number;
    Press: number;
    Count: number;
    EndPos: number;
    Billet_Length: number;
    
    // Temperatures
    Spot: number;
    Temp_F: number;
    Temp_B: number;
    Billet_Temp: number;
    
    // Molds
    Mold1: number;
    Mold2: number;
    Mold3: number;
    Mold4: number;
    Mold5: number;
    Mold6: number;
    
    // Environment
    At_Temp: number;
    At_Pre: number;
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
