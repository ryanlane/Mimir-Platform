/**
 * Weather Card Web Component
 * Displays current weather conditions in a dashboard widget
 */

class WeatherCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  async connectedCallback() {
    try {
      // Parse props passed from host
      const props = JSON.parse(this.getAttribute('data-hostprops') || '{}');
      const user = props.user || {};
      const theme = props.theme || 'light';
      
      // Fetch weather data from channel API
      const city = user.city || 'Seattle';
      const response = await fetch(
        `/api/channels/weather_channel/forecast?city=${encodeURIComponent(city)}`,
        { credentials: 'include' }
      );
      
      if (!response.ok) {
        throw new Error(`Weather API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Render weather card
      this.render(data, theme);
      
    } catch (error) {
      console.error('Weather card error:', error);
      this.renderError(error.message);
    }
  }

  render(weatherData, theme) {
    const isDark = theme === 'dark';
    const bgColor = isDark ? '#2d3748' : '#ffffff';
    const textColor = isDark ? '#e2e8f0' : '#2d3748';
    const borderColor = isDark ? '#4a5568' : '#e2e8f0';
    
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        
        .weather-card {
          background: ${bgColor};
          color: ${textColor};
          border: 1px solid ${borderColor};
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          max-width: 300px;
        }
        
        .weather-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        
        .city-name {
          font-size: 18px;
          font-weight: 600;
          margin: 0;
        }
        
        .temperature {
          font-size: 24px;
          font-weight: 700;
          color: #3182ce;
        }
        
        .condition {
          font-size: 14px;
          color: #718096;
          margin-bottom: 8px;
        }
        
        .details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          font-size: 12px;
        }
        
        .detail-item {
          display: flex;
          justify-content: space-between;
        }
        
        .forecast {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid ${borderColor};
        }
        
        .forecast-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 4px 0;
          font-size: 12px;
        }
        
        .error {
          color: #e53e3e;
          padding: 16px;
          text-align: center;
          font-size: 14px;
        }
      </style>
      
      <div class="weather-card">
        <div class="weather-header">
          <h3 class="city-name">${weatherData.city}</h3>
          <div class="temperature">${weatherData.current.tempC}°C</div>
        </div>
        
        <div class="condition">${weatherData.current.condition}</div>
        
        <div class="details">
          <div class="detail-item">
            <span>Humidity:</span>
            <span>${weatherData.current.humidity}%</span>
          </div>
          <div class="detail-item">
            <span>Wind:</span>
            <span>${weatherData.current.windSpeed} km/h</span>
          </div>
        </div>
        
        <div class="forecast">
          ${weatherData.forecast.slice(0, 3).map(day => `
            <div class="forecast-item">
              <span>${day.day}</span>
              <span>${day.high}°/${day.low}°</span>
              <span>${day.condition}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  renderError(message) {
    this.shadowRoot.innerHTML = `
      <style>
        .error {
          color: #e53e3e;
          padding: 16px;
          text-align: center;
          font-size: 14px;
          border: 1px solid #feb2b2;
          border-radius: 8px;
          background: #fed7d7;
        }
      </style>
      <div class="error">
        Weather unavailable: ${message}
      </div>
    `;
  }
}

// Register the custom element
customElements.define('x-weather-card', WeatherCard);

// Export for module systems
export { WeatherCard };
