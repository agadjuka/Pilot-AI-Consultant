import uvicorn

if __name__ == "__main__":
    print("\n" + "="*70)
    print("   🚀 Сервер для Webhook запущен")
    print("="*70)
    print(f"   📍 URL:         http://127.0.0.1:8001")
    print(f"   💚 Healthcheck: http://127.0.0.1:8001/healthcheck")
    print("-"*70)
    print("   ℹ️  Этот режим предназначен для продакшена.")
    print("   ℹ️  Для локальной разработки используйте: python run_polling.py")
    print("="*70 + "\n")
    
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)

