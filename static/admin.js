// Simple React admin board for the clinic queue.
// This script fetches the board state from the backend and renders it.

const e = React.createElement;

function AdminBoard() {
  const [passcode, setPasscode] = React.useState('');
  const [board, setBoard] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [isLoggedIn, setIsLoggedIn] = React.useState(false);

  const fetchBoard = () => {
    if (!passcode) return;
    fetch(`/admin/board?passcode=${encodeURIComponent(passcode)}`)
      .then((res) => {
        if (!res.ok) throw new Error('Invalid passcode or server error');
        return res.json();
      })
      .then((data) => {
        setBoard(data);
        setError(null);
        setIsLoggedIn(true);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoggedIn(false);
      });
  };

  React.useEffect(() => {
    if (isLoggedIn && passcode) {
      const id = setInterval(fetchBoard, 5000);
      return () => clearInterval(id);
    }
  }, [passcode, isLoggedIn]);

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchBoard();
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      fetchBoard();
    }
  };

  const handleAction = (code, action) => {
    fetch('/admin/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passcode, action, code }),
    })
      .then((res) => {
        if (!res.ok) throw new Error('Action failed');
        return res.json();
      })
      .then((data) => {
        setBoard(data);
      })
      .catch((err) => setError(err.message));
  };

  if (!isLoggedIn) {
    return e('div', { style: { padding: '20px', maxWidth: '400px', margin: '50px auto' } },
      e('h2', null, 'Clinic Queue Admin'),
      e('form', { onSubmit: handleSubmit },
        e('div', { style: { marginBottom: '10px' } },
          e('label', { style: { display: 'block', marginBottom: '5px' } }, 'Admin Passcode:'),
          e('input', {
            type: 'password',
            value: passcode,
            onChange: (e) => setPasscode(e.target.value),
            onKeyPress: handleKeyPress,
            placeholder: 'Enter passcode (default: demo)',
            style: { width: '100%', padding: '8px', fontSize: '16px' }
          })
        ),
        e('button', {
          type: 'submit',
          style: { 
            padding: '10px 20px', 
            fontSize: '16px', 
            backgroundColor: '#007bff', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }
        }, 'Login')
      ),
      error && e('p', { style: { color: 'red', marginTop: '10px' } }, error)
    );
  }

  if (!board) {
    return e('div', null, 'Loading...');
  }

  return e('div', null,
    e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' } },
      e('h1', null, board.clinic_name || 'Clinic Queue'),
      e('button', {
        onClick: () => { setIsLoggedIn(false); setBoard(null); setPasscode(''); },
        style: { padding: '5px 10px' }
      }, 'Logout')
    ),
    ['waiting', 'next', 'in_room', 'done', 'no_show'].map((status) =>
      e('div', { key: status },
        e('h3', null, status.replace('_', ' ').toUpperCase()),
        e('table', null,
          e('thead', null,
            e('tr', null,
              e('th', null, 'Code'),
              e('th', null, 'Phone'),
              e('th', null, 'Note'),
              e('th', null, 'Position'),
              e('th', null, 'ETA (min)'),
              e('th', null, 'Actions')
            )
          ),
          e('tbody', null,
            (board.tickets[status] || []).map((ticket) =>
              e('tr', { key: ticket.code },
                e('td', null, ticket.code),
                e('td', null, ticket.phone || 'N/A'),
                e('td', null, ticket.note || ''),
                e('td', null, ticket.position || ''),
                e('td', null, ticket.eta_minutes || ''),
                e('td', null,
                  status === 'waiting' && e('button', { onClick: () => handleAction(ticket.code, 'promote') }, 'Next'),
                  status === 'next' && e('button', { onClick: () => handleAction(ticket.code, 'in_room') }, 'In Room'),
                  status === 'in_room' && e('button', { onClick: () => handleAction(ticket.code, 'done') }, 'Done'),
                  status === 'waiting' && e('button', { onClick: () => handleAction(ticket.code, 'urgent') }, 'Urgent'),
                  ['waiting', 'next'].includes(status) && e('button', { onClick: () => handleAction(ticket.code, 'no_show') }, 'No Show'),
                  e('button', { onClick: () => handleAction(ticket.code, 'cancel') }, 'Cancel')
                )
              )
            )
          )
        )
      )
    )
  );
}

ReactDOM.render(e(AdminBoard), document.getElementById('app'));