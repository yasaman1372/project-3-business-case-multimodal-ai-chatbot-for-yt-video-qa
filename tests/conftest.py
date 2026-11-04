def pytest_addoption(parser):
    parser.addoption("--run-network", action="store_true", default=False,
                     help="Also run tests that call real external APIs (YouTube, OpenAI, Pinecone)")
