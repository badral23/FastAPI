FastAPI with Neon DB

This is a FastAPI application integrated with Neon DB (serverless PostgreSQL) for managing items with soft deletion and
timestamp tracking. The project uses SQLAlchemy for ORM, Pydantic for data validation, and organizes routes in a modular
structure.

## Project Structure

```
fastapi_neon/
├── routes/
│   ├── __init__.py
│   ├── item.py         # Item-related API routes
│   └── user.py         # Placeholder for user-related routes
├── .env                # Environment variables (Neon DB connection string)
├── main.py             # Main FastAPI application
├── database.py         # Database configuration (SQLAlchemy)
├── models.py           # SQLAlchemy models with BaseModelC/BaseModelCU
├── schemas.py          # Pydantic schemas for validation
├── crud.py             # CRUD operations for Item model
└── requirements.txt    # Project dependencies
```

## Features

- **Item Management**: CRUD operations for items with soft deletion.
- **Soft Deletion**: Items are marked as `deleted` instead of being removed, with support for hard deletion.
- **Timestamps**: Items track `created_at` timestamps using `BaseModelC`.
- **Neon DB**: Uses Neon DB's serverless PostgreSQL for data storage.
- **Modular Routes**: API endpoints organized in `routes/item.py` and `routes/user.py` (placeholder).
- **Swagger UI**: Interactive API documentation at `/docs`.

## Requirements

- Python 3.8+
- Neon DB account with a PostgreSQL database
- Virtual environment (recommended)

## Installation

1. **Clone the Repository** (or create the project structure manually):

   ```bash
   git clone <repository-url>
   cd fastapi_neon
   ```

2. **Set Up Virtual Environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   The `requirements.txt` includes:

    - `fastapi`
    - `uvicorn`
    - `sqlalchemy`
    - `psycopg2-binary`
    - `pydantic`
    - `python-dotenv`

4. **Configure Neon DB**:

    - Log in to your Neon DB dashboard (https://console.neon.tech).
    - Copy the connection string for your database (e.g.,
      `postgresql://username:password@ep-cool-project-123456.us-east-2.aws.neon.tech/dbname`).
    - Create a `.env` file in the project root:

      ```plaintext
      DATABASE_URL=postgresql://username:password@ep-cool-project-123456.us-east-2.aws.neon.tech/dbname?sslmode=require
      ```

      Replace with your actual Neon DB connection string.

5. **Run the Application**:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

    - The `--reload` flag enables auto-reload for development.
    - The API will be available at `http://0.0.0.0:8000`.
    - Access the Swagger UI at `http://0.0.0.0:8000/docs`.

## Usage

The application provides RESTful endpoints for managing items, all under the `/items` prefix. The `Item` model includes
`id`, `name`, `description`, `created_at`, and `deleted` fields, with soft deletion support.

### Available Endpoints

- **POST /items/**: Create a new item.

  ```bash
  curl -X POST "http://0.0.0.0:8000/items/" -H "Content-Type: application/json" -d '{"name":"Test Item","description":"This is a test item"}'
  ```

- **GET /items/**: Retrieve all items (excluding deleted by default).

  ```bash
  curl http://0.0.0.0:8000/items/
  ```

  Add `?include_deleted=true` to include soft-deleted items.

- **GET /items/{item_id}**: Retrieve a specific item by ID.

  ```bash
  curl http://0.0.0.0:8000/items/1
  ```

- **DELETE /items/{item_id}**: Soft delete an item (marks `deleted=true`).

  ```bash
  curl -X DELETE http://0.0.0.0:8000/items/1
  ```

- **DELETE /items/{item_id}/hard**: Hard delete an item (removes from database).

  ```bash
  curl -X DELETE http://0.0.0.0:8000/items/1/hard
  ```

- **GET /items/deleted/**: Retrieve all soft-deleted items.

  ```bash
  curl http://0.0.0.0:8000/items/deleted/
  ```

- **GET /items/count/**: Count items (excluding deleted by default).

  ```bash
  curl http://0.0.0.0:8000/items/count/
  ```

- **GET /users/**: Placeholder endpoint for user routes.

  ```bash
  curl http://0.0.0.0:8000/users/
  ```

### Testing

- Use the Swagger UI at `http://0.0.0.0:8000/docs` for interactive testing.
- Alternatively, use `curl`, Postman, or another HTTP client to test endpoints.
- To verify the database connection, use `psql`:

  ```bash
  psql "postgresql://username:password@ep-cool-project-123456.us-east-2.aws.neon.tech/dbname?sslmode=require"
  ```

  Check the `items` table:

  ```sql
  \dt
  SELECT * FROM items;
  ```

## Troubleshooting

- **Connection Errors**: Verify the `DATABASE_URL` in `.env`. Test the connection with `psql`. Ensure your network
  allows connections to Neon DB.
- **Table Not Created**: Ensure `main.py` runs `models.Base.metadata.create_all(bind=engine)` to create the `items`
  table in Neon DB.
- **Import Errors**: Confirm the `routes` directory has an `__init__.py` file and imports in `main.py` are correct (
  `from routes import item, user`).
- **Windows Issues**: Use backslashes for paths (e.g., `.\venv\Scripts\activate`). If `uvicorn` fails, try:

  ```bash
  python -m uvicorn main:app --host 0.0.0.0 --port 8000
  ```
- **SSL Issues**: Neon DB requires SSL. Ensure `sslmode=require` is in the `DATABASE_URL` if you encounter SSL errors.

## Development Notes

- **Soft Deletion**: The `Item` model uses `BaseModelC` for `created_at` and `deleted` fields, supporting soft deletion.
- **Modular Routes**: Item routes are in `routes/item.py`. Add user-related routes in `routes/user.py` as needed.
- **Neon DB**: The application is configured for Neon DB’s serverless PostgreSQL. Use Neon’s dashboard to manage
  databases and branches.
- **Production**: Replace `uvicorn --reload` with Gunicorn for production. Secure the `.env` file and add error
  handling.

## Future Enhancements

- Implement user-related endpoints in `routes/user.py` with a corresponding `User` model.
- Add authentication (e.g., JWT) for secure access.
- Implement pagination for large datasets.
- Add more complex queries or filters for items.

## License

This project is unlicensed. Modify and distribute as needed.