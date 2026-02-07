from typer.testing import CliRunner
from sqlmodel import Session, select
from pharmabot.main import app
from pharmabot.models import ProductCatalog, BasketItem

runner = CliRunner()


def test_add_product_with_minsan(session: Session):
    result = runner.invoke(
        app, ["catalog", "add", "--name", "Test Product", "--minsan", "123456"]
    )
    assert result.exit_code == 0
    assert "Product 'Test Product' added successfully" in result.stdout

    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()
    assert product is not None
    assert product.name == "Test Product"


def test_add_product_without_minsan(session: Session):
    result = runner.invoke(app, ["catalog", "add", "--name", "No Minsan Product"])
    assert result.exit_code == 0
    assert "Product 'No Minsan Product' added successfully" in result.stdout

    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.name == "No Minsan Product")
    ).first()
    assert product is not None
    assert product.minsan is None


def test_add_duplicate_minsan(session: Session):
    # Add first time
    runner.invoke(
        app, ["catalog", "add", "--name", "Product A", "--minsan", "123456"]
    )

    # Add duplicate minsan
    result = runner.invoke(
        app, ["catalog", "add", "--name", "Product B", "--minsan", "123456"]
    )
    assert result.exit_code == 1
    assert "Error: Product with minsan 123456 already exists" in result.stdout


def test_add_duplicate_name(session: Session):
    # Add first time
    runner.invoke(app, ["catalog", "add", "--name", "Unique Name"])

    # Add duplicate name
    result = runner.invoke(
        app, ["catalog", "add", "--name", "Unique Name", "--minsan", "999999"]
    )
    assert result.exit_code == 1
    assert "Error: Product with name 'Unique Name' already exists" in result.stdout


def test_list_products_empty(session: Session):
    result = runner.invoke(app, ["catalog", "list"])
    assert result.exit_code == 0
    assert "Product Catalog" in result.stdout
    assert "Minsan" in result.stdout
    assert "Name" in result.stdout


def test_list_products_populated(session: Session):
    runner.invoke(
        app, ["catalog", "add", "--name", "Product A", "--minsan", "123456"]
    )
    runner.invoke(app, ["catalog", "add", "--name", "Product B"])

    result = runner.invoke(app, ["catalog", "list"])
    assert result.exit_code == 0
    assert "123456" in result.stdout
    assert "Product A" in result.stdout
    assert "N/A" in result.stdout
    assert "Product B" in result.stdout


def test_update_product(session: Session):
    runner.invoke(
        app, ["catalog", "add", "--name", "Old Name", "--minsan", "123456"]
    )
    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()

    result = runner.invoke(
        app, ["catalog", "update", str(product.id), "--name", "New Name"]
    )
    assert result.exit_code == 0
    assert f"Product {product.id} updated successfully." in result.stdout

    session.refresh(product)
    assert product.name == "New Name"


def test_update_non_existent_product(session: Session):
    result = runner.invoke(app, ["catalog", "update", "999999", "--name", "New Name"])
    assert result.exit_code == 1
    assert "Error: Product with id 999999 not found" in result.stdout


def test_remove_product(session: Session):
    runner.invoke(
        app, ["catalog", "add", "--name", "To Remove", "--minsan", "123456"]
    )
    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()

    result = runner.invoke(app, ["catalog", "remove", str(product.id)])
    assert result.exit_code == 0
    assert f"Product {product.id} removed successfully." in result.stdout

    product_check = session.get(ProductCatalog, product.id)
    assert product_check is None


def test_remove_non_existent_product(session: Session):
    result = runner.invoke(app, ["catalog", "remove", "999999"])
    assert result.exit_code == 1
    assert "Error: Product with id 999999 not found" in result.stdout


def test_remove_product_cascade_basket(session: Session):
    runner.invoke(
        app,
        ["catalog", "add", "--name", "Product In Basket", "--minsan", "123456"],
    )
    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()

    basket_item = BasketItem(product_id=product.id, quantity=5)
    session.add(basket_item)
    session.commit()

    # Verify basket item exists
    assert (
        session.exec(
            select(BasketItem).where(BasketItem.product_id == product.id)
        ).first()
        is not None
    )

    # Remove product
    result = runner.invoke(app, ["catalog", "remove", str(product.id)])
    assert result.exit_code == 0

    # Verify product removed
    assert session.get(ProductCatalog, product.id) is None

    # Verify basket item removed
    assert (
        session.exec(
            select(BasketItem).where(BasketItem.product_id == product.id)
        ).first()
        is None
    )
