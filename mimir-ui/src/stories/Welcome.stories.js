// More on how to set up stories at: https://storybook.js.org/docs/writing-stories#default-export
const meta = {
  title: 'Mimir/Welcome',
  parameters: {
    // Optional parameter to center the component in the Canvas. More info: https://storybook.js.org/docs/configure/story-layout
    layout: 'fullscreen',
  },
  // More on argTypes: https://storybook.js.org/docs/api/argtypes
  argTypes: {},
};

export default meta;

// More on writing stories with args: https://storybook.js.org/docs/writing-stories/args
export const Welcome = {
  render: () => (
    <div style={{
      padding: '48px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <h1 style={{ 
        color: '#1e293b',
        marginBottom: '24px',
        fontSize: '2.5rem',
        fontWeight: '700'
      }}>
        🎭 Mimir UI Storybook
      </h1>
      
      <p style={{ 
        fontSize: '1.125rem',
        color: '#64748b',
        marginBottom: '32px',
        lineHeight: '1.6'
      }}>
        Welcome to the Mimir UI component library! This Storybook contains all the reusable 
        components used in the Mimir multi-display management system.
      </p>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        marginBottom: '32px'
      }}>
        <div style={{
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '24px',
          backgroundColor: '#f8fafc'
        }}>
          <h3 style={{ 
            marginTop: '0',
            marginBottom: '12px',
            color: '#1e293b',
            fontSize: '1.25rem'
          }}>
            🧩 Components
          </h3>
          <p style={{ 
            color: '#64748b',
            fontSize: '0.875rem',
            lineHeight: '1.5',
            margin: '0'
          }}>
            Explore reusable UI components like buttons, modals, loading states, and more.
          </p>
        </div>

        <div style={{
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '24px',
          backgroundColor: '#f8fafc'
        }}>
          <h3 style={{ 
            marginTop: '0',
            marginBottom: '12px',
            color: '#1e293b',
            fontSize: '1.25rem'
          }}>
            🎬 Mimir Specific
          </h3>
          <p style={{ 
            color: '#64748b',
            fontSize: '0.875rem',
            lineHeight: '1.5',
            margin: '0'
          }}>
            See components designed specifically for the Mimir platform like scene cards and display status.
          </p>
        </div>
      </div>

      <div style={{
        backgroundColor: '#dbeafe',
        border: '1px solid #93c5fd',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '32px'
      }}>
        <h3 style={{ 
          marginTop: '0',
          marginBottom: '12px',
          color: '#1e40af',
          fontSize: '1.125rem'
        }}>
          🚀 Getting Started
        </h3>
        <ul style={{ 
          color: '#1e40af',
          fontSize: '0.875rem',
          lineHeight: '1.5',
          margin: '0',
          paddingLeft: '20px'
        }}>
          <li>Browse the components in the sidebar</li>
          <li>Each component has multiple stories showing different states</li>
          <li>Use the Controls panel to interact with component props</li>
          <li>Check the Docs tab for detailed documentation</li>
        </ul>
      </div>

      <div style={{
        borderTop: '1px solid #e2e8f0',
        paddingTop: '24px'
      }}>
        <h3 style={{ 
          marginTop: '0',
          marginBottom: '16px',
          color: '#1e293b',
          fontSize: '1.125rem'
        }}>
          📋 Component Categories
        </h3>
        
        <div style={{ display: 'grid', gap: '12px' }}>
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>🔘</span>
            <div>
              <strong style={{ color: '#1e293b' }}>Components/Button</strong>
              <span style={{ color: '#64748b', marginLeft: '8px' }}>- All button variants and states</span>
            </div>
          </div>
          
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>🪟</span>
            <div>
              <strong style={{ color: '#1e293b' }}>Components/Modal</strong>
              <span style={{ color: '#64748b', marginLeft: '8px' }}>- Modal dialogs and overlays</span>
            </div>
          </div>
          
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>⏳</span>
            <div>
              <strong style={{ color: '#1e293b' }}>Components/Loading</strong>
              <span style={{ color: '#64748b', marginLeft: '8px' }}>- Loading spinners and states</span>
            </div>
          </div>
          
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>🎭</span>
            <div>
              <strong style={{ color: '#1e293b' }}>Mimir/SceneCard</strong>
              <span style={{ color: '#64748b', marginLeft: '8px' }}>- Scene management cards</span>
            </div>
          </div>
          
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            backgroundColor: '#f1f5f9',
            borderRadius: '6px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>📡</span>
            <div>
              <strong style={{ color: '#1e293b' }}>Components/WebSocketStatus</strong>
              <span style={{ color: '#64748b', marginLeft: '8px' }}>- Connection status indicators</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  ),
};
