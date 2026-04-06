/**
 * Weather Page Component
 * Full-page weather interface with detailed forecast
 */

class WeatherPage extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  async connectedCallback() {
    try {
      const props = JSON.parse(this.getAttribute('data-hostprops') || '{}');
      const user = props.user || {};
      const theme = props.theme || 'light';
      
      // Fetch detailed weather data
      const city = user.city || 'Seattle';
      const response = await fetch(
        `/api/channels/weather_channel/forecast?city=${encodeURIComponent(city)}`,
        { credentials: 'include' }
      );
      
      const data = await response.json();
      this.render(data, theme);
      
    } catch (error) {
      console.error('Weather page error:', error);
      this.renderError(error.message);
    }
  }

  render(weatherData, theme) {
    const isDark = theme === 'dark';
    const bgColor = isDark ? '#1a202c' : '#f7fafc';
    const cardBg = isDark ? '#2d3748' : '#ffffff';
    const textColor = isDark ? '#e2e8f0' : '#2d3748';
    
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: ${bgColor};
          min-height: 100vh;
          padding: 20px;
        }
        
        .weather-page {
          max-width: 1200px;
          margin: 0 auto;
          color: ${textColor};
        }
        
        .page-header {
          text-align: center;
          margin-bottom: 30px;
        }
        
        .page-title {
          font-size: 32px;
          font-weight: 700;
          margin: 0 0 8px 0;
        }
        
        .page-subtitle {
          font-size: 16px;
          color: #718096;
        }
        
        .weather-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          margin-bottom: 30px;
        }
        
        .weather-card {
          background: ${cardBg};
          border-radius: 12px;
          padding: 24px;
          box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .current-weather {
          text-align: center;
        }
        
        .current-temp {
          font-size: 48px;
          font-weight: 700;
          color: #3182ce;
          margin: 16px 0;
        }
        
        .current-condition {
          font-size: 18px;
          color: #718096;
          margin-bottom: 20px;
        }
        
        .weather-details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        
        .detail-group {
          text-align: center;
        }
        
        .detail-label {
          font-size: 12px;
          color: #718096;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        
        .detail-value {
          font-size: 18px;
          font-weight: 600;
          margin-top: 4px;
        }
        
        .forecast-section {
          background: ${cardBg};
          border-radius: 12px;
          padding: 24px;
          box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .section-title {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 20px;
        }
        
        .forecast-list {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
        }
        
        .forecast-item {
          background: ${bgColor};
          border-radius: 8px;
          padding: 16px;
          text-align: center;
        }
        
        .forecast-day {
          font-weight: 600;
          margin-bottom: 8px;
        }
        
        .forecast-temps {
          font-size: 18px;
          margin: 8px 0;
        }
        
        .forecast-condition {
          font-size: 14px;
          color: #718096;
        }
        
        @media (max-width: 768px) {
          .weather-grid {
            grid-template-columns: 1fr;
          }
          
          .forecast-list {
            grid-template-columns: 1fr;
          }
        }
      </style>
      
      <div class="weather-page">
        <div class="page-header">
          <h1 class="page-title">Weather Forecast</h1>
          <p class="page-subtitle">Current conditions and forecast for ${weatherData.city}</p>
        </div>
        
        <div class="weather-grid">
          <div class="weather-card current-weather">
            <h2>Current Conditions</h2>
            <div class="current-temp">${weatherData.current.tempC}°C</div>
            <div class="current-condition">${weatherData.current.condition}</div>
            
            <div class="weather-details">
              <div class="detail-group">
                <div class="detail-label">Humidity</div>
                <div class="detail-value">${weatherData.current.humidity}%</div>
              </div>
              <div class="detail-group">
                <div class="detail-label">Wind Speed</div>
                <div class="detail-value">${weatherData.current.windSpeed} km/h</div>
              </div>
            </div>
          </div>
          
          <div class="weather-card">
            <h2>Quick Stats</h2>
            <div class="weather-details">
              <div class="detail-group">
                <div class="detail-label">Feels Like</div>
                <div class="detail-value">${weatherData.current.tempC + 2}°C</div>
              </div>
              <div class="detail-group">
                <div class="detail-label">UV Index</div>
                <div class="detail-value">5</div>
              </div>
              <div class="detail-group">
                <div class="detail-label">Visibility</div>
                <div class="detail-value">10 km</div>
              </div>
              <div class="detail-group">
                <div class="detail-label">Pressure</div>
                <div class="detail-value">1013 hPa</div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="forecast-section">
          <h2 class="section-title">Extended Forecast</h2>
          <div class="forecast-list">
            ${weatherData.forecast.map(day => `
              <div class="forecast-item">
                <div class="forecast-day">${day.day}</div>
                <div class="forecast-temps">${day.high}° / ${day.low}°</div>
                <div class="forecast-condition">${day.condition}</div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  renderError(message) {
    this.shadowRoot.innerHTML = `
      <div style="padding: 40px; text-align: center; color: #e53e3e;">
        <h2>Weather Unavailable</h2>
        <p>${message}</p>
      </div>
    `;
  }
}

customElements.define('x-weather-page', WeatherPage);
export { WeatherPage };
