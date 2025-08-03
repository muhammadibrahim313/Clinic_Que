// Enhanced React Admin Dashboard for Clinic Queue with Analytics
// This provides a comprehensive dashboard with real-time metrics, charts, and queue management

const e = React.createElement;

function AdminDashboard() {
  const [passcode, setPasscode] = React.useState('');
  const [isLoggedIn, setIsLoggedIn] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState('overview');
  const [error, setError] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  
  // Data states
  const [board, setBoard] = React.useState(null);
  const [analytics, setAnalytics] = React.useState(null);
  const [metrics, setMetrics] = React.useState(null);
  const [timeline, setTimeline] = React.useState([]);
  
  // Chart references
  const hourlyChartRef = React.useRef(null);
  const statusChartRef = React.useRef(null);
  const channelChartRef = React.useRef(null);

  // Authentication
  const handleLogin = async (e) => {
    e.preventDefault();
    if (!passcode) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/admin/board?passcode=${encodeURIComponent(passcode)}`);
      if (!response.ok) throw new Error('Invalid passcode');
      
      const data = await response.json();
      setBoard(data);
      setIsLoggedIn(true);
      await loadAllData();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setIsLoggedIn(false);
    setBoard(null);
    setAnalytics(null);
    setMetrics(null);
    setTimeline([]);
    setPasscode('');
    setActiveTab('overview');
  };

  // Data fetching
  const loadAllData = async () => {
    if (!passcode) return;
    
    try {
      const [analyticsRes, metricsRes, timelineRes] = await Promise.all([
        fetch(`/admin/analytics?passcode=${encodeURIComponent(passcode)}`),
        fetch(`/admin/metrics?passcode=${encodeURIComponent(passcode)}`),
        fetch(`/admin/timeline?passcode=${encodeURIComponent(passcode)}`)
      ]);

      if (analyticsRes.ok) {
        const analyticsData = await analyticsRes.json();
        setAnalytics(analyticsData);
      }

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      if (timelineRes.ok) {
        const timelineData = await timelineRes.json();
        setTimeline(timelineData.timeline || []);
      }
    } catch (err) {
      console.error('Error loading data:', err);
    }
  };

  const refreshBoard = async () => {
    if (!passcode) return;
    
    try {
      const response = await fetch(`/admin/board?passcode=${encodeURIComponent(passcode)}`);
      if (response.ok) {
        const data = await response.json();
        setBoard(data);
      }
    } catch (err) {
      console.error('Error refreshing board:', err);
    }
  };

  // Real-time updates
  React.useEffect(() => {
    if (!isLoggedIn || !passcode) return;

    // Setup Server-Sent Events for real-time updates
    const eventSource = new EventSource(`/admin/events?passcode=${encodeURIComponent(passcode)}`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'board_update' && data.data) {
          setBoard(data.data);
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = () => {
      console.log('SSE connection failed, falling back to polling');
      eventSource.close();
    };

    // Refresh data periodically
    const dataInterval = setInterval(loadAllData, 30000); // Every 30 seconds
    const metricsInterval = setInterval(async () => {
      if (passcode) {
        try {
          const response = await fetch(`/admin/metrics?passcode=${encodeURIComponent(passcode)}`);
          if (response.ok) {
            const data = await response.json();
            setMetrics(data);
          }
        } catch (err) {
          console.error('Error refreshing metrics:', err);
        }
      }
    }, 10000); // Every 10 seconds

    return () => {
      eventSource.close();
      clearInterval(dataInterval);
      clearInterval(metricsInterval);
    };
  }, [isLoggedIn, passcode]);

  // Chart creation
  React.useEffect(() => {
    if (!analytics || activeTab !== 'analytics') return;

    // Hourly Distribution Chart
    if (hourlyChartRef.current) {
      const ctx = hourlyChartRef.current.getContext('2d');
      const hours = Array.from({length: 24}, (_, i) => i);
      const data = hours.map(h => analytics.hourly_distribution[h] || 0);

      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: hours.map(h => `${h}:00`),
          datasets: [{
            label: 'Patients',
            data: data,
            backgroundColor: 'rgba(102, 126, 234, 0.6)',
            borderColor: 'rgba(102, 126, 234, 1)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: { beginAtZero: true }
          }
        }
      });
    }

    // Status Distribution Chart
    if (statusChartRef.current) {
      const ctx = statusChartRef.current.getContext('2d');
      const statuses = Object.keys(analytics.status_counts);
      const counts = Object.values(analytics.status_counts);
      const colors = [
        '#fbbf24', '#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#6b7280'
      ];

      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: statuses.map(s => s.replace('_', ' ').toUpperCase()),
          datasets: [{
            data: counts,
            backgroundColor: colors.slice(0, statuses.length),
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'bottom' }
          }
        }
      });
    }

    // Channel Distribution Chart
    if (channelChartRef.current) {
      const ctx = channelChartRef.current.getContext('2d');
      const channels = Object.keys(analytics.channel_stats);
      const counts = Object.values(analytics.channel_stats);

      new Chart(ctx, {
        type: 'pie',
        data: {
          labels: channels.map(c => c.toUpperCase()),
          datasets: [{
            data: counts,
            backgroundColor: ['#8b5cf6', '#06b6d4', '#84cc16'],
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'bottom' }
          }
        }
      });
    }
  }, [analytics, activeTab]);

  // Action handler
  const handleAction = async (code, action) => {
    try {
      const response = await fetch('/admin/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passcode, action, code }),
      });

      if (!response.ok) throw new Error('Action failed');
      
      const data = await response.json();
      setBoard(data);
      
      // Refresh other data after action
      setTimeout(loadAllData, 1000);
    } catch (err) {
      setError(err.message);
    }
  };

  // Helper functions
  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString();
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status) => {
    const colors = {
      waiting: 'orange',
      next: 'blue', 
      in_room: 'orange',
      done: 'green',
      no_show: 'red',
      urgent: 'red',
      canceled: 'gray'
    };
    return colors[status] || 'gray';
  };

  const getEventIcon = (eventType, status) => {
    const icons = {
      joined: '🎫',
      promoted: '⬆️',
      done: '✅',
      no_show: '❌',
      canceled: '🚫',
      notified_next: '🔔'
    };
    return icons[eventType] || '📝';
  };

  // Login screen
  if (!isLoggedIn) {
    return e('div', { className: 'login-container' },
      e('div', { className: 'login-card' },
        e('div', { className: 'login-title' }, 
          e('i', { className: 'fas fa-hospital-user', style: { marginRight: '0.5rem' } }),
          'Clinic Queue Admin'
        ),
        e('form', { onSubmit: handleLogin },
          e('div', { className: 'form-group' },
            e('label', { className: 'form-label' }, 'Admin Passcode'),
            e('input', {
              type: 'password',
              className: 'form-input',
              value: passcode,
              onChange: (e) => setPasscode(e.target.value),
              placeholder: 'Enter your passcode',
              disabled: loading,
              autoComplete: 'new-password'
            })
          ),
          e('button', {
            type: 'submit',
            className: 'btn-primary',
            disabled: loading || !passcode.trim()
          }, loading ? 'Logging in...' : 'Login')
        ),
        error && e('div', { className: 'error-message' }, error)
      )
    );
  }

  // Main dashboard
  return e('div', { className: 'dashboard' },
    // Header
    e('div', { className: 'header' },
      e('h1', null, 
        e('i', { className: 'fas fa-clinic-medical', style: { marginRight: '0.5rem' } }),
        'Clinic Queue Dashboard'
      ),
      e('button', { className: 'btn-logout', onClick: logout },
        e('i', { className: 'fas fa-sign-out-alt', style: { marginRight: '0.5rem' } }),
        'Logout'
      )
    ),

    // Navigation
    e('div', { className: 'nav-tabs' },
      ['overview', 'queue', 'analytics', 'timeline'].map(tab =>
        e('button', {
          key: tab,
          className: `nav-tab ${activeTab === tab ? 'active' : ''}`,
          onClick: () => setActiveTab(tab)
        }, 
          e('i', { 
            className: tab === 'overview' ? 'fas fa-tachometer-alt' :
                      tab === 'queue' ? 'fas fa-users' :
                      tab === 'analytics' ? 'fas fa-chart-bar' :
                      'fas fa-history',
            style: { marginRight: '0.5rem' }
          }),
          tab.charAt(0).toUpperCase() + tab.slice(1)
        )
      )
    ),

    // Content
    e('div', { className: 'content' },
      // Overview Tab
      activeTab === 'overview' && e('div', null,
        metrics && e('div', { className: 'metrics-grid' },
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon blue' },
              e('i', { className: 'fas fa-users' })
            ),
            e('div', { className: 'metric-value' }, metrics.queue_length),
            e('div', { className: 'metric-label' }, 'In Queue')
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon orange' },
              e('i', { className: 'fas fa-clock' })
            ),
            e('div', { className: 'metric-value' }, `${metrics.estimated_wait_minutes}m`),
            e('div', { className: 'metric-label' }, 'Est. Wait Time')
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon green' },
              e('i', { className: 'fas fa-check-circle' })
            ),
            e('div', { className: 'metric-value' }, metrics.today_completed),
            e('div', { className: 'metric-label' }, 'Completed Today')
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon blue' },
              e('i', { className: 'fas fa-chart-line' })
            ),
            e('div', { className: 'metric-value' }, metrics.patients_per_hour.toFixed(1)),
            e('div', { className: 'metric-label' }, 'Patients/Hour')
          )
        ),

        // Quick Queue Overview
        board && board.tickets && e('div', { className: 'queue-grid' },
          ['waiting', 'next', 'in_room'].map(status => {
            const tickets = (board.tickets && board.tickets[status]) || [];
            const headerClass = status.replace('_', '-');
            
            return e('div', { key: status, className: 'queue-section' },
              e('div', { className: `queue-header ${headerClass}` },
                status.replace('_', ' ').toUpperCase(),
                e('span', { style: { float: 'right' } }, `(${tickets.length})`)
              ),
              e('div', { className: 'ticket-list' },
                tickets.slice(0, 5).map(ticket =>
                  e('div', { key: ticket.code, className: 'ticket-item' },
                    e('div', { className: 'ticket-info' },
                      e('div', { className: 'ticket-code' }, ticket.code),
                      e('div', { className: 'ticket-details' },
                        ticket.position && `#${ticket.position} • `,
                        ticket.eta_minutes && `${ticket.eta_minutes}m • `,
                        ticket.note && ticket.note.substring(0, 20) + (ticket.note.length > 20 ? '...' : '')
                      )
                    )
                  )
                ),
                tickets.length > 5 && e('div', { 
                  style: { padding: '0.5rem 1.5rem', color: '#6b7280', fontSize: '0.875rem' }
                }, `+${tickets.length - 5} more`)
              )
            );
          })
        )
      ),

      // Queue Management Tab
      activeTab === 'queue' && board && board.tickets && e('div', null,
        e('div', { className: 'queue-grid' },
          ['waiting', 'next', 'in_room', 'done', 'no_show'].map(status => {
            const tickets = (board.tickets && board.tickets[status]) || [];
            const headerClass = status.replace('_', '-');
            
            return e('div', { key: status, className: 'queue-section' },
              e('div', { className: `queue-header ${headerClass}` },
                status.replace('_', ' ').toUpperCase(),
                e('span', { style: { float: 'right' } }, `(${tickets.length})`)
              ),
              e('div', { className: 'ticket-list' },
                tickets.map(ticket =>
                  e('div', { key: ticket.code, className: 'ticket-item' },
                    e('div', { className: 'ticket-info' },
                      e('div', { className: 'ticket-code' }, ticket.code),
                      e('div', { className: 'ticket-details' },
                        ticket.position && `Position: #${ticket.position} • `,
                        ticket.eta_minutes && `ETA: ${ticket.eta_minutes}m • `,
                        'Created: ', formatTime(ticket.created_at),
                        ticket.note && e('br'),
                        ticket.note && e('span', { style: { fontStyle: 'italic' } }, ticket.note)
                      )
                    ),
                    e('div', { className: 'ticket-actions' },
                      status === 'waiting' && [
                        e('button', { 
                          key: 'promote',
                          className: 'btn btn-sm btn-blue',
                          onClick: () => handleAction(ticket.code, 'promote')
                        }, 'Next'),
                        e('button', { 
                          key: 'urgent',
                          className: 'btn btn-sm btn-red',
                          onClick: () => handleAction(ticket.code, 'urgent')
                        }, 'Urgent')
                      ],
                      status === 'next' && e('button', { 
                        className: 'btn btn-sm btn-orange',
                        onClick: () => handleAction(ticket.code, 'in_room')
                      }, 'In Room'),
                      status === 'in_room' && e('button', { 
                        className: 'btn btn-sm btn-green',
                        onClick: () => handleAction(ticket.code, 'done')
                      }, 'Done'),
                      ['waiting', 'next'].includes(status) && e('button', { 
                        className: 'btn btn-sm btn-gray',
                        onClick: () => handleAction(ticket.code, 'no_show')
                      }, 'No Show'),
                      ['waiting', 'next', 'in_room'].includes(status) && e('button', { 
                        className: 'btn btn-sm btn-gray',
                        onClick: () => handleAction(ticket.code, 'cancel')
                      }, 'Cancel')
                    )
                  )
                )
              )
            );
          })
        )
      ),

      // Analytics Tab
      activeTab === 'analytics' && analytics && e('div', null,
        e('div', { className: 'metrics-grid' },
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon blue' },
              e('i', { className: 'fas fa-ticket-alt' })
            ),
            e('div', { className: 'metric-value' }, analytics.total_tickets),
            e('div', { className: 'metric-label' }, `Total Tickets (${analytics.days_analyzed} days)`)
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon green' },
              e('i', { className: 'fas fa-percentage' })
            ),
            e('div', { className: 'metric-value' }, `${analytics.completion_rate}%`),
            e('div', { className: 'metric-label' }, 'Completion Rate')
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon orange' },
              e('i', { className: 'fas fa-clock' })
            ),
            e('div', { className: 'metric-value' }, `${analytics.avg_wait_minutes}m`),
            e('div', { className: 'metric-label' }, 'Avg Wait Time')
          ),
          e('div', { className: 'metric-card' },
            e('div', { className: 'metric-icon red' },
              e('i', { className: 'fas fa-user-times' })
            ),
            e('div', { className: 'metric-value' }, `${analytics.no_show_rate}%`),
            e('div', { className: 'metric-label' }, 'No-Show Rate')
          )
        ),

        e('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' } },
          e('div', { className: 'chart-container' },
            e('div', { className: 'chart-title' }, 'Hourly Patient Distribution (Today)'),
            e('canvas', { ref: hourlyChartRef, style: { maxHeight: '300px' } })
          ),
          e('div', { className: 'chart-container' },
            e('div', { className: 'chart-title' }, 'Status Distribution'),
            e('canvas', { ref: statusChartRef, style: { maxHeight: '300px' } })
          ),
          e('div', { className: 'chart-container' },
            e('div', { className: 'chart-title' }, 'Channel Distribution'),
            e('canvas', { ref: channelChartRef, style: { maxHeight: '300px' } })
          )
        )
      ),

      // Timeline Tab
      activeTab === 'timeline' && e('div', null,
        e('div', { className: 'timeline' },
          e('div', { className: 'timeline-header' },
            e('h3', null, 'Recent Patient Activity'),
            e('p', { style: { color: '#6b7280', marginTop: '0.5rem' } }, 
              'Last 24 hours of patient flow events'
            )
          ),
          e('div', { className: 'timeline-body' },
            timeline.length === 0 ? 
              e('div', { className: 'loading' }, 'No recent activity') :
              timeline.map((event, index) =>
                e('div', { key: index, className: 'timeline-item' },
                  e('div', { 
                    className: `timeline-icon ${getStatusColor(event.status)}`,
                    style: {
                      backgroundColor: getStatusColor(event.status) === 'blue' ? '#dbeafe' :
                                    getStatusColor(event.status) === 'green' ? '#dcfce7' :
                                    getStatusColor(event.status) === 'orange' ? '#fed7aa' :
                                    getStatusColor(event.status) === 'red' ? '#fecaca' : '#f3f4f6',
                      color: getStatusColor(event.status) === 'blue' ? '#1d4ed8' :
                            getStatusColor(event.status) === 'green' ? '#166534' :
                            getStatusColor(event.status) === 'orange' ? '#c2410c' :
                            getStatusColor(event.status) === 'red' ? '#dc2626' : '#6b7280'
                    }
                  }, getEventIcon(event.event_type, event.status)),
                  e('div', { className: 'timeline-content' },
                    e('div', null,
                      e('strong', null, `${event.code} `),
                      `(${event.phone}) `,
                      event.event_type === 'joined' ? 'joined the queue' :
                      event.event_type === 'promoted' ? 'was called next' :
                      event.event_type === 'done' ? 'completed visit' :
                      event.event_type === 'no_show' ? 'marked as no-show' :
                      event.event_type === 'canceled' ? 'canceled visit' :
                      `status changed to ${event.status}`,
                      event.channel && ` via ${event.channel.toUpperCase()}`
                    ),
                    e('div', { className: 'timeline-time' },
                      formatTime(event.event_time || event.updated_at),
                      event.note && ` • ${event.note}`
                    )
                  )
                )
              )
          )
        )
      )
    )
  );
}

// Mount the application using React 18 createRoot API
const root = ReactDOM.createRoot(document.getElementById('app'));
root.render(e(AdminDashboard));