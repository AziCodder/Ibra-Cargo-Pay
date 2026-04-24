import { Button, Result, theme } from 'antd';
import { useNavigate } from 'react-router-dom';

const { useToken } = theme;

export default function NotFoundPage() {
  const navigate = useNavigate();
  const { token } = useToken();

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: token.colorBgLayout,
      }}
    >
      <Result
        status="404"
        title="404"
        subTitle="Страница не найдена"
        extra={
          <Button type="primary" onClick={() => navigate('/', { replace: true })}>
            На главную
          </Button>
        }
      />
    </div>
  );
}
